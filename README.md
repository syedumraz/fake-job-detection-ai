# AI Against Fraud: Lightweight & Transparent Detection of Fake Job Postings

Full-stack machine learning web application developed for my M.Tech thesis at **P.D.A. College of Engineering, Kalaburagi (VTU)** and published in **IJCISIM (2026)**.

## Publications
- **Journal Paper:** **S. Umraz, R. B.K.**, *"A Lightweight, Transparent Machine Learning System for Real-Time Detection of Fraudulent Online Job Postings,"* International Journal of Computer Information Systems and Industrial Management Applications (IJCISIM), Vol. 18, Sept. 2026. | **DOI:** `10.70917/ijcisim-2026-5736` | [Read Paper](https://cspub-ijcisim.org/index.php/ijcisim/article/view/5736)
- **Survey Paper:** **S. Umraz, R. B.K.**, *"Comprehensive Review of Detection of Fake Job Listing Using AI,"* Journal of Scientific Research and Technology (ISSN: 2583-8660), Vol. 4, Issue 6, pp. 94–102, June 2026. | **DOI:** `10.5281/zenodo.20584049` | [Read Paper](https://jsrtjournal.com/index.php/JSRT/article/view/470)

## Overview
Online recruitment scams pose serious financial and privacy risks to job seekers. Unlike heavy black-box deep learning models, this system focuses on **low computational overhead (real-time speed)** and **model transparency (explainability)** to flag fraudulent job descriptions accurately.

## Key Features
- **Text Preprocessing & Feature Engineering:** Automated cleaning, tokenization, and TF-IDF vectorization of job titles, company profiles, and descriptions.
- **Class Imbalance & Lightweight Classification:** Uses SMOTE balancing alongside Passive Aggressive Classifier, Multi-Layer Perceptron (MLP), Random Forest, Logistic Regression, and KNN for fast, low-latency inference.
- **Model Transparency:** Interpretable feature weights showing *why* a posting was flagged as fraudulent.
