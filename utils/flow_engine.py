import threading
import subprocess
import time
import asyncio
from datetime import datetime, timedelta
import logging
import os
from typing import Dict, Any, List, Optional
from data.flow_registry import FlowRegistry
from utils.flow_executor import FlowExecutor
from utils.credentials_store import get_credential, list_credentials
from utils.session import get_session_password, get_session_owner

logger = logging.getLogger("flow_engine")

class FlowEngine:
    def __init__(self):
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._running_flows: Dict[str, bool] = {}

    def start(self):
        if self._thread and self._thread.is_alive():
            return
            
        # Orphaned Run Protection
        # If the app crashed previously while flows were RUNNING, reset them.
        flows = FlowRegistry.get_all_flows()
        for flow in flows:
            if flow.get("status") == "RUNNING":
                logger.warning(f"Flow {flow['id']} was stuck in RUNNING state on startup. Resetting to ERROR.")
                FlowRegistry.update_flow(flow["id"], {"status": "ERROR"})
                # Automatically log the orphan crash
                execution_data = {
                    "flow_id": flow["id"],
                    "timestamp": datetime.now().isoformat(),
                    "duration": "0s",
                    "status": "Failed",
                    "logs": "System Warning: Flow was interrupted by an application crash or abrupt shutdown."
                }
                try:
                    FlowRegistry.add_execution(execution_data)
                except Exception:
                    pass

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._engine_loop, daemon=True)
        if self._thread:
            self._thread.start()
        logger.info("Flow Engine started.")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        logger.info("Flow Engine stopped.")


    def stop_flow(self, flow_id: str):
        if flow_id in self._running_flows:
            process = self._running_flows[flow_id]
            if isinstance(process, subprocess.Popen):
                logger.info(f"Stopping flow {flow_id}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                
            self._running_flows.pop(flow_id, None)
            FlowRegistry.update_flow(flow_id, {"status": "ABORTED"})
            
            # Add an execution entry for the abortion
            execution_data = {
                "flow_id": flow_id,
                "timestamp": datetime.now().isoformat(),
                "duration": "0s",
                "status": "Aborted",
                "logs": "Flow was manually stopped by the user."
            }
            try:
                FlowRegistry.add_execution(execution_data)
            except Exception:
                pass
            
            logger.info(f"Flow {flow_id} stopped.")

    def _engine_loop(self):
        while not self._stop_event.is_set():
            current_owner = get_session_owner()
            flows = FlowRegistry.get_all_flows()
            for flow in flows:
                # Only run flows owned by the currently logged-in user.
                # We can't decrypt another user's credential-bound flow anyway.
                if current_owner is None or flow.get("owner") != current_owner:
                    continue
                if flow.get("enabled", False) and flow["id"] not in self._running_flows:
                    if self._should_run(flow):
                        self.trigger_flow(flow)

            time.sleep(10) # Check every 10 seconds

    def _should_run(self, flow: Dict[str, Any]) -> bool:
        schedule_type = flow.get("schedule_type")
        last_run_str = flow.get("last_run")
        
        if not last_run_str:
            return True # Never run before

        try:
            last_run = datetime.fromisoformat(last_run_str)
        except ValueError:
            return True
        
        if schedule_type == "Interval":
            minutes = flow.get("interval_minutes", 15)
            return datetime.now() >= last_run + timedelta(minutes=minutes)
        
        if schedule_type == "Continuous":
            last_completed_str = flow.get("last_completed")
            if last_completed_str:
                try:
                    last_completed = datetime.fromisoformat(last_completed_str)
                    if datetime.now() < last_completed + timedelta(seconds=30):
                        return False
                except ValueError:
                    pass
            return True

        return False

    def trigger_flow(self, flow: Dict[str, Any]):
        flow_id = flow["id"]
        # We store a placeholder first, will be updated with process handle in the task
        self._running_flows[flow_id] = True

        # Run in separate thread to not block engine loop
        threading.Thread(target=self._run_flow_task, args=(flow,), daemon=True).start()

    def _run_flow_task(self, flow: Dict[str, Any]):
        flow_id = flow["id"]
        try:
            self._execute_flow_task_inner(flow)
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            logger.error(f"Unhandled exception in Flow Task: {error_msg}")
            
            # Write to a file aggressively for debugging
            with open(os.path.join(os.path.dirname(__file__), "crash_log.txt"), "a") as f:
                f.write(f"[{datetime.now().isoformat()}] CRASH for {flow_id}:\n{error_msg}\n")
                
            FlowRegistry.update_flow(flow_id, {"status": "ERROR"})
            
            execution_data = {
                "flow_id": flow_id,
                "timestamp": datetime.now().isoformat(),
                "duration": "0s",
                "status": "ERROR",
                "logs": f"Engine Crash: {error_msg}"
            }
            try:
                FlowRegistry.add_execution(execution_data)
            except Exception:
                pass
        finally:
            self._running_flows.pop(flow_id, None)

    def _execute_flow_task_inner(self, flow: Dict[str, Any]):
        flow_id = flow["id"]
        script_path = flow["script_path"]
        params = flow.get("params", {})
        credential_ids = FlowRegistry.get_credential_ids(flow)

        flow_updates = {}

        # Mark as running
        FlowRegistry.update_flow(flow_id, {"status": "RUNNING", "last_run": datetime.now().isoformat()})

        credentials_by_name: Dict[str, Dict[str, Any]] = {}
        if credential_ids:
            owner = get_session_owner()
            password = get_session_password()
            if not owner or not password:
                msg = "Credential decryption failed — please re-login to run this flow."
                logger.error(f"Flow {flow_id}: {msg}")
                FlowRegistry.update_flow(flow_id, {"status": "ERROR"})
                FlowRegistry.add_execution({
                    "flow_id": flow_id,
                    "timestamp": datetime.now().isoformat(),
                    "duration": "0s",
                    "status": "Failed",
                    "logs": msg,
                })
                return

            name_by_id = {c["id"]: c["name"] for c in list_credentials(owner)}

            for cid in credential_ids:
                fields = get_credential(owner, cid, password)
                name = name_by_id.get(cid)
                if fields is None or not name:
                    msg = (
                        f"Credential decryption failed for id={cid} — "
                        "credential may have been deleted or the password is wrong."
                    )
                    logger.error(f"Flow {flow_id}: {msg}")
                    FlowRegistry.update_flow(flow_id, {"status": "ERROR"})
                    FlowRegistry.add_execution({
                        "flow_id": flow_id,
                        "timestamp": datetime.now().isoformat(),
                        "duration": "0s",
                        "status": "Failed",
                        "logs": msg,
                    })
                    return
                credentials_by_name[name] = fields

        process, start_time_iso = FlowExecutor.start_script(
            script_path, params, credentials=credentials_by_name
        )
        # Wipe plaintext credentials from parent memory once the subprocess
        # has its own copy in its environment block.
        del credentials_by_name

        if not process:
            FlowRegistry.update_flow(flow_id, {"status": "ERROR"})
            return

        # Update running flows with actual process handle
        self._running_flows[flow_id] = process
        
        start_time = time.time()
        
        # Wait for process and capture output safely
        import queue
        log_queue = queue.Queue()
        
        def pipe_reader(pipe, q):
            try:
                for line in iter(pipe.readline, ""):
                    if not line:
                        break
                    q.put(line)
            except Exception:
                pass

        logs_lines = []
        try:
            # Start background thread to read stdout continuously without blocking
            reader_thread = None
            if process.stdout:
                reader_thread = threading.Thread(target=pipe_reader, args=(process.stdout, log_queue), daemon=True)
                reader_thread.start()

            # Poll the process to check for abortion without blocking forever
            while True:
                # Drain queue to our logs
                while not log_queue.empty():
                    logs_lines.append(log_queue.get_nowait())

                # Check for abortion during execution
                current_flow = FlowRegistry.get_flow(flow_id)
                if current_flow and current_flow.get("status") == "ABORTED":
                    process.terminate()
                    flow_updates.update({"status": "ABORTED"})
                    success = False
                    logs_lines.append("\n[Process aborted by user]")
                    break
                    
                try:
                    # Wait for process to finish with a small timeout
                    process.wait(timeout=1.0)
                    break  # Process finished
                except subprocess.TimeoutExpired:
                    # Process is still running, loop continues to check abort status
                    continue

            # Process finished or aborted. Drain remaining logs.
            if reader_thread:
                reader_thread.join(timeout=2.0)
            while not log_queue.empty():
                logs_lines.append(log_queue.get_nowait())

            if flow_updates.get("status") != "ABORTED":
                success = process.returncode == 0
            
            logs = "".join(logs_lines)
            
        except Exception as e:
            success = False
            logs = "".join(logs_lines) + f"\nError during execution: {e}"
            
        duration = round(time.time() - start_time, 2)
            
        if flow_updates.get("status") == "ABORTED":
            status = "ABORTED"
        else:
            status = "Success" if success else "Failed"
            flow_updates.update({
                "status": status,
                "last_completed": datetime.now().isoformat()
            })
            
        # Save execution history FIRST so UI doesn't race when updating state to Success
        execution_data = {
            "flow_id": flow_id,
            "timestamp": start_time_iso,
            "duration": f"{duration}s",
            "status": "Failed" if status == "ABORTED" else status,
            "logs": logs if logs else "No Output"
        }
        FlowRegistry.add_execution(execution_data)
        
        # Then update metrics and status
        FlowRegistry.update_flow(flow_id, flow_updates)

# Singleton instance
engine = FlowEngine()
