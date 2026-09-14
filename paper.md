---

title: "CYBERPULSE AI: An Open-Source Cybercrime Intelligence Platform for Predictive Cash-Withdrawal Risk Analysis"
tags:

- cybersecurity
- financial fraud
- machine learning
- anomaly detection
- graph analytics
- explainable artificial intelligence
- cybercrime intelligence
- fraud detection
  authors:
- name: "R. Vetrivel"
  orcid: "[ADD ORCID]"
  affiliation: "Department of Electronics and Communication Engineering, Central University of Karnataka, India"
  corresponding: true
  email: "[ADD EMAIL]"
  date: 2026-09-15
  bibliography: references.bib
  repository-code: "https://github.com/[USERNAME]/[REPOSITORY]"
  license: "MIT"

---

Summary

CYBERPULSE AI is an open-source cybercrime intelligence and financial-fraud research platform for analyzing and predicting suspicious cash-withdrawal activity. It combines supervised machine learning, anomaly detection, temporal features, entity-relationship analysis, historical behavior, explainable artificial intelligence (XAI), and interactive visualization in a single research software system.

The platform represents cybercrime and financial-transaction activity as point-in-time prediction units associated with individual automated teller machines (ATMs) and time windows. A machine-learning model estimates the probability of suspicious cash-out activity in a future window, while complementary anomaly, graph, temporal, and historical signals are incorporated into a configurable risk engine. The resulting score is presented on a 0--100 scale together with an interpretable risk band, SHAP-based explanatory features, and a recommended operational action.

CYBERPULSE AI also provides a research-oriented investigation environment. Predictions can generate alerts, which can subsequently be acknowledged, escalated, investigated, and resolved. Investigations maintain case status, notes, event timelines, linked entities, and generated PDF reports. An interactive map provides spatial exploration of ATMs, withdrawals, complaints, and predicted risk. A controlled simulation can replay a synthetic fraud-ring lifecycle to support reproducible experimentation and demonstrations.

The current implementation consists of a FastAPI backend, React/Vite frontend, machine-learning pipeline, SQLite demonstration database, optional graph and cache integrations, WebSocket-based real-time updates, and automated setup and verification scripts. All demonstration entities and transactions are synthetic.

Statement of Need

Financial fraud and cyber-enabled cash-out activity often involve multiple weak signals distributed across time, geography, accounts, complaints, and transaction behavior. A monitoring system that considers only individual transactions can therefore miss coordinated patterns that emerge across several entities and time periods.

Research on fraud detection commonly focuses on individual machine-learning models, transaction classification, anomaly detection, graph-based fraud analysis, or visualization systems. Although these approaches are valuable individually, researchers and practitioners often need to combine several analytical perspectives while preserving temporal consistency and interpretability.

CYBERPULSE AI addresses this software gap by providing an integrated research platform in which prediction, anomaly analysis, graph relationships, temporal behavior, explainability, visualization, and investigation workflows can be studied together. The software is intended for researchers and developers working on financial-fraud detection, cybercrime intelligence, anomaly detection, explainable machine learning, graph analytics, and decision-support systems.

A central design objective is reproducibility. The platform generates a deterministic synthetic environment, trains the prediction model from the generated data, stores evaluation artifacts, and exposes the same point-in-time feature construction mechanism for both training and inference. This enables researchers to modify feature definitions, model parameters, risk-engine weights, simulation conditions, and downstream investigation workflows without reconstructing the entire system independently.

The software is explicitly a research prototype and is not intended to make operational law-enforcement or banking decisions. Its demonstration environment uses synthetic data only.

State of the Field

Existing open-source libraries provide strong capabilities for individual components of the CYBERPULSE AI workflow. General machine-learning frameworks support supervised classification; anomaly-detection libraries support unsupervised and semi-supervised detection; graph libraries support network analysis; explainability frameworks support model interpretation; and geospatial visualization libraries support interactive mapping.

CYBERPULSE AI does not attempt to replace these specialized libraries. Instead, it provides an integrated experimental environment that combines them around a common cybercrime-intelligence workflow. The software contribution is therefore at the system level: it establishes a reproducible pipeline connecting point-in-time feature construction, prediction, risk fusion, explainability, spatial visualization, entity relationships, alert generation, investigation management, and report generation.

An important implementation decision is to retain established open-source components for their specialized capabilities rather than reimplementing equivalent algorithms. The platform therefore acts as an integration and experimentation layer over mature machine-learning, graph, visualization, and web-development technologies.

The repository should additionally document specific related packages and research systems used for comparison, together with a clear build-versus-contribute justification for each major dependency.

Software Design

CYBERPULSE AI is organized into four principal layers: data and feature engineering, predictive and risk analysis, application services, and the user interface.

The machine-learning layer generates synthetic transaction, complaint, ATM, account, and temporal information and transforms these data into point-in-time prediction units. A shared "FeatureContext" implementation computes the feature vector for both model training and live inference. This design avoids maintaining separate feature-engineering implementations for training and serving, thereby reducing the possibility of train/serve feature skew.

The current feature pipeline contains 27 features covering temporal, spatial, financial, and network-related information. The prediction target is defined as the occurrence of at least three withdrawals in the subsequent six-hour window. The primary classifier is an XGBoost model, with logistic regression provided as a baseline. Model artifacts and evaluation information are stored in the repository so that experiments can be reproduced without relying on undocumented external state.

The risk engine combines the machine-learning probability with complementary signals:

$$
R = P_{ML} + B(A + G + T + H)
$$

where $P_{ML}$ is the model probability, $A$ is the anomaly signal, $G$ is the graph-related signal, $T$ is the temporal signal, $H$ is the historical-behavior signal, and $B$ represents the configurable boost factor. The resulting value is transformed into a bounded 0--100 risk score and assigned to a risk band.

This architecture deliberately separates predictive probability from secondary contextual signals. Researchers can therefore evaluate the predictive model independently and subsequently investigate how additional signals influence operational prioritization.

Explainability is provided using SHAP-based feature attribution. For a high-risk prediction, the system exposes the principal contributing features rather than presenting the risk score as an unexplained classification result.

The backend is implemented using FastAPI and exposes authentication, prediction, alert, investigation, graph, map, model, simulation, reporting, and real-time services. WebSocket events allow prediction generation and simulation events to be reflected in the frontend without requiring continuous manual refresh.

The frontend is implemented using React and Vite. Leaflet provides geographic visualization and Recharts provides analytical plots. Optional Neo4j and Redis integrations can be enabled for deployments requiring external graph storage or distributed real-time infrastructure; the demonstration configuration can operate using SQLite and an in-process real-time mechanism.

A key design trade-off is complexity versus research flexibility. A single monolithic prediction service would be simpler to deploy, but separating data generation, feature engineering, model inference, risk fusion, API services, visualization, and investigation workflows makes controlled experiments easier and allows individual components to be replaced.

Research Impact Statement

CYBERPULSE AI is intended to provide a reproducible research environment for studying predictive financial-fraud and cybercrime-intelligence workflows rather than serving as a production banking or law-enforcement system.

The included synthetic environment enables experiments involving coordinated behavioral patterns such as complaint surges, suspicious account activity, reconnaissance-like behavior, and subsequent cash-withdrawal bursts. Researchers can use the simulation and what-if functionality to evaluate how changes in temporal, transaction, complaint, and spatial signals affect predicted risk.

The repository includes a trained model, generated datasets, preprocessing code, evaluation artifacts, database seeding utilities, and API verification scripts. This enables a researcher to reproduce the demonstration environment and investigate alternative models, features, thresholds, and risk-fusion strategies.

In the current demonstration evaluation, the XGBoost classifier achieves a test AUC of approximately 0.96 on the included synthetic evaluation dataset. This value is an evaluation result of the supplied synthetic environment and should not be interpreted as evidence of real-world fraud-detection performance. The software has not been validated on confidential banking, law-enforcement, or real customer transaction data.

Before submission, the repository should document concrete evidence of research use, such as an independent research experiment, reproducible benchmark, publication or preprint using CYBERPULSE AI, external integration, or documented use by researchers outside the development process. Such evidence is particularly important because JOSS evaluates demonstrated research impact rather than future potential.

AI Usage Disclosure

Generative artificial-intelligence tools were used during the development and/or documentation of CYBERPULSE AI [UPDATE THIS SECTION TO MATCH THE ACTUAL DEVELOPMENT HISTORY].

Where AI-assisted generation was used, generated code, documentation, and manuscript text were reviewed and tested by the authors. Software functionality was verified through automated endpoint checks, execution of the demonstration workflow, model evaluation artifacts, and manual inspection of the resulting application.

AI-generated content was not treated as an independent source of scientific evidence. Performance claims, software behavior, references, experimental results, and technical descriptions included in this article should be verified against the corresponding repository artifacts and primary sources before submission.

Acknowledgements

The authors acknowledge the open-source software communities whose libraries and development tools support CYBERPULSE AI.

[ADD FUNDING INFORMATION OR STATE: "No specific funding was received for this work."]

References

The following references should be completed with the exact versions, authors, venues, and DOIs where applicable before submission.

- Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining. https://doi.org/10.1145/2939672.2939785

- Lundberg, S. M., & Lee, S.-I. (2017). A unified approach to interpreting model predictions. Advances in Neural Information Processing Systems, 30.

- McKinney, W. (2010). Data structures for statistical computing in Python. Proceedings of the 9th Python in Science Conference.

- Pedregosa, F., et al. (2011). Scikit-learn: Machine learning in Python. Journal of Machine Learning Research, 12, 2825--2830.

- [ADD REFERENCE FOR THE GRAPH-ANALYTICS LIBRARY ACTUALLY USED]

- [ADD REFERENCE FOR THE ANOMALY-DETECTION LIBRARY ACTUALLY USED]

- [ADD REFERENCE FOR THE GEOSPATIAL/VISUALIZATION SOFTWARE ACTUALLY USED]

- [ADD REFERENCE FOR THE FASTAPI/REACT OR OTHER SOFTWARE COMPONENTS WHERE APPROPRIATE]

- [ADD CYBERPULSE AI SOFTWARE ARCHIVE/DOI AFTER ZENODO ARCHIVAL]
