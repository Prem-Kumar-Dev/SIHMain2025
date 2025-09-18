# `nextStep.md`: Implementing the Advanced GNN Predictive Core

## 1. Objective

You have successfully implemented a foundational predictive engine with a baseline regressor and a Torch MLP, along with the necessary API endpoints (`/predict`, `/resolve`). The next critical step is to build and integrate the advanced **Graph Neural Network (GNN)** model to replace the simple MLP.

The primary goal of this phase is to leverage the railway network's structure to significantly improve prediction accuracy and the effectiveness of conflict detection. The GNN will learn from the complex interactions between trains and sections, something a standard MLP cannot do.

## 2. Development Roadmap

This phase focuses on implementing the GNN, training it on your simulated data, and integrating it into the existing application workflow.

### **Module 1: GNN Model Implementation**

This is the core development task. You will replace the stubs in `gnn/graph_builder.py` and `gnn/model_stub.py` with a fully functional model.

*   **Task 1.1: Implement the Graph Builder (`gnn/graph_builder.py`)**
    *   Convert the `{ sections, trains }` state into a graph data structure compatible with a GNN library like **PyTorch Geometric (PyG)**.
    *   The graph should be heterogeneous: node types Train and Section; edge types Train→Train (headway), Train→Section (location/next), Section→Section (topology).

*   **Task 1.2: Build the GNN Model (`gnn/model_gnn.py`)**
    *   Implement a Heterogeneous Graph Neural Network (e.g., SAGE-Het). The model outputs train-node embeddings and a small MLP head predicts delay minutes.

### **Module 2: Model Training and Validation**

*   **Task 2.1:** Use `generate_training_data.py` to create a large dataset with varied scenarios.
*   **Task 2.2:** Implement `gnn/train_gnn.py` to construct graphs with the GraphBuilder and train the GNN using MSE.
*   **Task 2.3:** Evaluate on a held-out test set, compare against the Torch MLP (MAE/RMSE), and save weights `gnn_delay_predictor.pt`.

### **Module 3: Integration and System Enhancement**

*   **Task 3.1:** Update `/predict` to support `?model=baseline|mlp|gnn|auto` (env default `PREDICTIVE_MODEL_KIND`) and load weights via `PREDICTIVE_MODEL_PATH` when needed.
*   **Task 3.2:** In the UI (Live Dashboard), add a model selector and visualize predictions on the Gantt.

## 3. Definition of Done for This Phase

*   `GraphBuilder` and a functional GNN are implemented under `src/ai_core/predictive_engine/gnn/`.
*   A training script exists and produces a saved model.
*   Benchmarks show the GNN outperforms the Torch MLP on the same test set.
*   `/predict` integrates the trained GNN and gracefully falls back when needed.
*   UI can select and visualize the chosen predictor.

## 4. Next Step After This Phase: Reinforcement Learning

Once your system can make highly accurate predictions, introduce an RL agent for automated dispatching, using GNN embeddings as the state representation.