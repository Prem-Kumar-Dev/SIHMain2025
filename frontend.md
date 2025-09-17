

# `frontend.md`: Building the Controller Command & Control Interface (C3I)

## 1\. Objective

The goal of this phase is to develop a professional, intuitive, and highly functional frontend application that serves as the primary interface for the train traffic controller. This C3I will consume the existing backend API to provide a comprehensive decision-support tool.

The core design philosophy is **augmented intelligence**: the system provides powerful insights and recommendations, but the human controller always remains in command. The UI must be designed to reduce cognitive load and present complex information in a clear, actionable format.[1]

## 2\. Technology Stack

  * **Framework**: Streamlit (as currently used). It is excellent for rapid development and data-centric applications.
  * **Visualization**: Plotly (already in use). It is powerful enough for the required Gantt charts and KPI dashboards.
  * **API Communication**: A dedicated API client module using Python's `requests` library to handle all interactions with the backend.
  * **State Management**: Streamlit's `st.session_state` for maintaining user session information across interactions.

## 3\. Frontend Project Structure

To ensure modularity and separation from the backend, the `ui/` directory should be structured as follows:

```
ui/
├── app.py                 # Main application entry point (router for pages)
├── api_client.py          # Centralized module for all backend API calls
├── state_manager.py       # Helper functions for managing session state
├── pages/
│   ├── 1_Live_Dashboard.py  # Main view for real-time monitoring and control
│   └── 2_Scenario_Analysis.py # View for managing and running saved scenarios
└── components/
    ├── gantt_chart.py       # Logic for generating all Gantt chart visualizations
    ├── kpi_display.py       # Component for displaying KPI metrics
    └── scenario_editor.py   # The JSON editor and scenario management forms
```

## 4\. Development Roadmap & Core Functionalities

This roadmap breaks down the frontend development into logical, self-contained modules.

### **Module 1: The API Client (`api_client.py`)**

This is the foundational module for the frontend. It will abstract all backend communication, making the UI code clean and focused only on presentation.

  * **Task 1.1: Base Client Setup**:

      * Create a class `ApiClient` that takes the backend base URL from an environment variable.
      * Implement methods for handling authentication headers (if any) and standardizing error handling.

  * **Task 1.2: Implement Endpoint Functions**:

      * Create a dedicated function for every single API endpoint you have built. For example:
          * `get_live_snapshot(state, max_trains)` -\> calls `POST /live/snapshot`
          * `predict_delays(state)` -\> calls `POST /predict`
          * `resolve_conflicts(state, conflicts)` -\> calls `POST /resolve`
          * `run_whatif(state, solver, otp_tolerance)` -\> calls `POST /whatif`
          * `save_scenario(payload)`, `get_scenarios()`, `run_saved_scenario(sid, name)` etc. for all persistence endpoints.

### **Module 2: Live Dashboard Page (`pages/1_Live_Dashboard.py`)**

This will be the primary screen for a traffic controller, focusing on real-time operations.

  * **Task 2.1: Real-Time Network State Display**:

      * On page load, use the `api_client` to call the `/live/snapshot` endpoint.
      * Display the current train and section data in a simple, readable format. Add a "Refresh Live Data" button.

  * **Task 2.2: The Predictive Gantt Chart (`components/gantt_chart.py`)**:

      * This is the most critical UI component. It must visualize multiple layers of information clearly.[1]
      * Fetch the current state and pass it to the `/predict` endpoint to get predicted delays and conflicts.
      * The Gantt chart should display:
        1.  **Scheduled Path**: A baseline reference from the original timetable.
        2.  **Actual Path**: The historical track of the train up to the current time.
        3.  **Predicted Path**: The future trajectory of the train based on the AI model's predictions.
        4.  **Conflict Highlighting**: Clearly mark the points on the chart where the `/predict` endpoint has identified a future conflict.

  * **Task 2.3: Interactive Conflict Resolution Workflow**:

      * When a conflict is detected and displayed, the UI should automatically call the `/resolve` endpoint with the conflict data.
      * Present the returned solution to the user in a dedicated "Resolution Advisory" panel.
      * **Display Recommendation**: Show a plain-language summary (e.g., "Hold Train 'B' at Section 'S1' to resolve conflict with Train 'A'").
      * **Display Predicted Outcome**: Show the KPIs from the `/resolve` response to quantify the benefit of the action (e.g., "Expected Outcome: Average delay reduced to 2.5 mins").
      * **Provide Action Buttons**: Include `and` buttons. Clicking "Accept" would trigger the implementation of the resolved schedule.

### **Module 3: Scenario Analysis Page (`pages/2_Scenario_Analysis.py`)**

This page will house the powerful "what-if" and planning capabilities of your system, leveraging the persistence API.

  * **Task 3.1: Scenario Management Panel (`components/scenario_editor.py`)**:

      * Build a clean UI for listing, loading, saving, and deleting scenarios using the `/scenarios` endpoints.
      * Integrate the existing JSON editor for creating and modifying scenario payloads.

  * **Task 3.2: "What-If" Analysis Workflow**:

      * Allow the user to load a scenario into the editor.
      * Provide a "Run What-If" button that calls the `/whatif` endpoint.
      * Display the resulting Gantt chart, KPIs, and lateness table, allowing the controller to test different operational strategies before committing them.

  * **Task 3.3: Historical Run Analysis**:

      * When a user runs a saved scenario, it creates a `run` in the database.
      * Create a view to list all historical runs for a given scenario (`GET /scenarios/{sid}/runs`).
      * Allow the user to select a past run and view its full results (schedule, KPIs, lateness data) by calling `GET /runs/{rid}`.
      * Integrate the "Download Lateness CSV" button to call the `GET /runs/{rid}/lateness.csv` endpoint.

## 5\. Next Steps After Frontend

Once this frontend is complete, you will have a fully-fledged, pre-qualifier-ready SIH project that covers the entire pipeline from data modeling and optimization to prediction and user interaction.

The next logical step for the backend would be to implement the advanced GNN model as planned, which will make the predictions displayed in your new frontend even more accurate and powerful.