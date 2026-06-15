# Project Overview

## Project Purpose

This project is a desktop-based workflow automation platform built with Python and Flet. Its main goal is to help users create, manage, and run automated script-based flows, while also keeping database credentials secure and tracking execution history.

In simple terms, this app works like a lightweight automation dashboard for running Python scripts with scheduling, access control, licensing, and monitoring.

---

## What the application does

The app allows users to:

- Sign in and create accounts
- Manage user roles and password policies
- Activate a paid license or use a trial period
- Create and manage automated flows
- Run flows manually or automatically based on schedule
- View execution history and logs
- Store and manage database credentials securely
- Test database connections before saving credentials
- Use built-in CLI access for DuckDB, Polars, and Python

---

## Main Features

### 1. User authentication and access control

- Login screen with username/password
- Registration flow for new users
- Password strength validation
- Password reset/change flow
- Role-based access (admin vs regular user)

### 2. License and trial management

- Supports paid license activation
- Includes a 30-day trial mode
- Uses HWID-based validation for license locking
- Shows license info in the UI

### 3. Flow management

- Add new flows
- Edit existing flows
- Delete flows
- Enable/disable flows
- Search flows
- View flow status
- Run flows manually
- Track last run time and execution state

### 4. Scheduling and execution engine

- Supports interval-based scheduling
- Supports continuous execution mode
- Runs Python scripts in separate processes
- Tracks execution status: Running, Success, Failed, Aborted, Error
- Stops running flows when requested
- Handles flow crashes and marks them appropriately

### 5. Execution history and logs

- Stores flow execution history
- Displays timestamps, duration, and status
- Shows detailed logs for each run
- Keeps history limited to recent entries per flow

### 6. Secure credential storage

- Stores credentials per user
- Encrypts sensitive values before saving them
- Allows editing and deleting credentials
- Supports search in the credentials list
- Offers database connection testing before saving

### 7. Database and SQL tooling integration

- Supports credential-based database connection setup
- Can test connections for common database types such as PostgreSQL, MySQL, MariaDB, MSSQL, Oracle, and DB2
- Provides CLI access for SQL/data processing tools

### 8. UI and usability

- Modern desktop-style interface using Flet
- Sidebar navigation for Flows and Credentials
- Search bars and action buttons for managing records
- License info panel and hardware ID display

---

## High-Level Architecture

The project is organized into a few main areas:

- Views: UI screens such as login, register, home, license
- Components: reusable UI widgets like flow list, credentials list, dialogs
- Routes: navigation handling for the app
- Utils: core logic for auth, flow execution, licensing, credentials, sessions, and helpers
- Data: persistence files and registry logic for flows and executions

---

## Storage and persistence

The app uses:

- SQLite for users and encrypted credentials
- JSON files for flow definitions and execution history
- Local license and trial files for activation state

---

## Typical user workflow

1. Open the app
2. Log in or register
3. Activate a license or use the trial
4. Add database credentials
5. Create a flow by pointing to a Python script
6. Configure schedule and optional credentials
7. Run the flow manually or let the scheduler execute it
8. Monitor status and logs from the dashboard

---

## Summary

This project is essentially a desktop automation tool for running Python-based workflows, storing secure credentials, monitoring executions, and controlling access through authentication and licensing.

It is best suited for users who want a simple internal automation dashboard with:

- flow orchestration
- script execution
- credential safety
- execution monitoring
- licensing/trial support

---

## Suggested next steps

If you want, I can also create a more detailed version of this file with:

- screenshots/feature sections
- setup instructions
- architecture diagram
- developer notes for contributors
