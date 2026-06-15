import json
import os
import threading
from typing import List, Dict, Any, Optional
import uuid

FLOWS_FILE = os.path.join(os.path.dirname(__file__), "flows.json")
EXECUTIONS_FILE = os.path.join(os.path.dirname(__file__), "flow_executions.json")

_registry_lock = threading.RLock()

class FlowRegistry:
    @staticmethod
    def _read_flows() -> List[Dict[str, Any]]:
        with _registry_lock:
            if not os.path.exists(FLOWS_FILE):
                return []
            try:
                with open(FLOWS_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []

    @staticmethod
    def _write_flows(flows: List[Dict[str, Any]]):
        with _registry_lock:
            try:
                with open(FLOWS_FILE, "w") as f:
                    json.dump(flows, f, indent=4)
            except IOError as e:
                print(f"Error writing to {FLOWS_FILE}: {e}")

    @classmethod
    def get_all_flows(cls) -> List[Dict[str, Any]]:
        return cls._read_flows()

    @classmethod
    def get_flows_for(cls, owner: Optional[str], is_admin: bool = False) -> List[Dict[str, Any]]:
        """Return flows visible to this user.
        - Admins see all flows (including legacy flows with no owner).
        - Regular users see only flows whose owner matches their username.
        """
        flows = cls._read_flows()
        if is_admin:
            return flows
        if not owner:
            return []
        return [f for f in flows if f.get("owner") == owner]

    @classmethod
    def get_flow(cls, flow_id: str) -> Optional[Dict[str, Any]]:
        flows = cls._read_flows()
        for flow in flows:
            if flow["id"] == flow_id:
                return flow
        return None

    @staticmethod
    def get_credential_ids(flow: Dict[str, Any]) -> List[int]:
        """Return the list of credential IDs attached to a flow.

        New flows store `credential_ids: list[int]`. Legacy flows stored a
        single `credential_id: int | None`. This normalizes both shapes.
        """
        ids = flow.get("credential_ids")
        if isinstance(ids, list):
            return [int(i) for i in ids if i is not None]
        legacy = flow.get("credential_id")
        if legacy is None:
            return []
        return [int(legacy)]

    @classmethod
    def add_flow(cls, flow_config: Dict[str, Any]) -> str:
        flows = cls._read_flows()
        if "id" not in flow_config:
            flow_config["id"] = str(uuid.uuid4())

        # Default status and metrics
        flow_config.setdefault("status", "IDLE")
        flow_config.setdefault("last_run", None)
        flow_config.setdefault("next_run", None)
        flow_config.setdefault("created_at", None)  # Could add a timestamp

        flows.append(flow_config)
        cls._write_flows(flows)
        return flow_config["id"]

    @classmethod
    def update_flow(cls, flow_id: str, updates: Dict[str, Any]) -> bool:
        flows = cls._read_flows()
        for i, flow in enumerate(flows):
            if flow["id"] == flow_id:
                flows[i].update(updates)
                cls._write_flows(flows)
                return True
        return False

    @classmethod
    def delete_flow(cls, flow_id: str) -> bool:
        flows = cls._read_flows()
        deleted_flow = next((f for f in flows if f["id"] == flow_id), None)
        new_flows = [f for f in flows if f["id"] != flow_id]
        if len(new_flows) < len(flows):
            cls._write_flows(new_flows)
            # Optionally also delete its executions here
            executions = cls.get_all_executions()
            new_executions = [e for e in executions if e.get("flow_id") != flow_id]
            cls._write_executions(new_executions)

            # Clean up copied scripts in assets/scripts folder
            if deleted_flow:
                script_path = deleted_flow.get("script_path", "")
                if script_path and "assets/scripts" in script_path.replace("\\", "/") and os.path.exists(script_path):
                    try:
                        os.remove(script_path)
                    except Exception as e:
                        print(f"Failed to delete script file {script_path}: {e}")

            return True
        return False

    @staticmethod
    def _read_executions() -> List[Dict[str, Any]]:
        with _registry_lock:
            if not os.path.exists(EXECUTIONS_FILE):
                return []
            try:
                with open(EXECUTIONS_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []

    @staticmethod
    def _write_executions(executions: List[Dict[str, Any]]):
        with _registry_lock:
            try:
                with open(EXECUTIONS_FILE, "w") as f:
                    json.dump(executions, f, indent=4)
            except IOError as e:
                print(f"Error writing to {EXECUTIONS_FILE}: {e}")

    @classmethod
    def get_all_executions(cls) -> List[Dict[str, Any]]:
        return cls._read_executions()

    @classmethod
    def get_executions(cls, flow_id: str) -> List[Dict[str, Any]]:
        executions = cls._read_executions()
        return [e for e in executions if e.get("flow_id") == flow_id]

    @classmethod
    def add_execution(cls, execution_data: Dict[str, Any]) -> str:
        executions = cls._read_executions()
        if "id" not in execution_data:
            execution_data["id"] = str(uuid.uuid4())
        
        executions.append(execution_data)

        # Enforce auto-retention: max 50 logs per flow
        flow_id = execution_data.get("flow_id")
        if flow_id:
            flow_execs = [e for e in executions if e.get("flow_id") == flow_id]
            if len(flow_execs) > 50:
                # Sort by timestamp (oldest first)
                flow_execs.sort(key=lambda x: x.get("timestamp", ""))
                # Identify the oldest ones to delete
                ids_to_remove = {e["id"] for e in flow_execs[:-50]}
                executions = [e for e in executions if e["id"] not in ids_to_remove]

        cls._write_executions(executions)
        return execution_data["id"]

    @classmethod
    def clear_executions(cls, flow_id: str) -> bool:
        executions = cls._read_executions()
        new_executions = [e for e in executions if e.get("flow_id") != flow_id]
        if len(new_executions) < len(executions):
            cls._write_executions(new_executions)
            return True
        return False

