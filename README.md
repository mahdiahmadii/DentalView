# 🦷 DentalView
<img width="114" height="114" alt="m-ZGjReOSRPAnTRIR5WFld1noiw-7Cq3jfqZT7yjNJ_NwUWxUw" src="https://github.com/user-attachments/assets/2bc083a0-27f7-4405-bc5d-340e246e23fc" />


> An intelligent, offline desktop application for computer-aided detection of dental anomalies in panoramic X-ray (OPG) images.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.0+-green.svg)](https://pypi.org/project/PySide6/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Nano-orange.svg)](https://github.com/ultralytics/ultralytics)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Demo](#demo)
- [Architecture](#architecture)
- [Model Performance](#-model-performance)
- [Installation](#-installation)
- [Usage](#-usage)
- [Technologies](#technologies)
- [Project Structure](#-project-structure)
- [Contributing](#-contributing)
- [License](#-license)
- [Acknowledgments](#-acknowledgments)

---

## 🔍 Overview  <a id="overview"></a>

**DentalView** is a privacy-focused, locally-executed desktop application designed to assist dental professionals in identifying anomalies in panoramic radiographs (OPG images). Built with a layered architecture, it combines AI-powered detection with manual annotation capabilities, providing a comprehensive workflow from patient management to report generation.

### Why This Tool?

- **Privacy-First**: Fully offline operation—no internet connection required, ensuring patient data remains secure within your clinic.
- **AI-Assisted Diagnosis**: Leverages a custom-trained YOLOv8 Nano model with attention mechanisms for fast, accurate detection on standard hardware.
- **Doctor-AI Collaboration**: Dentists can add, edit, or refine AI-detected findings with manual annotations and clinical notes.
- **Complete Workflow**: From patient intake and case management to PDF report generation—all in one application.

---

## ✨ Key Features <a id="key-features"></a>


### 🧑‍⚕️ Patient & Case Management
- **Patient Database**: Store patient demographics (name, ID, DOB, phone, notes) in a local SQLite database.
- **Case History**: Organize multiple OPG images per patient with timestamps, labels, and custom notes.
- **Search & Filter**: Quickly retrieve patient records and case history.

### 🤖 AI-Powered Detection 
- **YOLOv8 Nano Model**: Lightweight object detection optimized for dental anomalies.
- **31 Detection Classes**: Trained on 24,000+ patient OPG images (public Kaggle dataset); exact benchmark metrics pending publication.
- **Asynchronous Inference**: Non-blocking model loading and detection via QThread workers.
- **Confidence Threshold**: Adjustable per-case confidence levels to filter detections.

### ✏️ Manual Annotation & Editing
- **Interactive Canvas**: Draw bounding boxes directly on images for manual findings.
- **Add/Edit Findings**: Supplement or correct AI detections with clinical observations.
- **Dual Source Tracking**: All findings are tagged as `ai` (model-generated) or `dentist` (manual) for transparency.

### 📊 Reporting & Export
- **PDF Medical Reports**: Auto-generate comprehensive reports with:
  - Analyzed image with bounding boxes
  - Findings table (class, confidence, source, notes)
  - Clinical summary and dentist notes
- **CSV/Excel Export**: Export findings data for external analysis.

### 🖼️ Image Handling
- **Zoom & Pan**: High-resolution image viewing with smooth zoom controls.
- **Annotated Image Save**: Original and annotated images stored separately.
- **Coordinate Transformation**: Precise mapping between display canvas and actual image coordinates.

---

## 🎬 Demo <a id="demo"></a>

### Application Interface
<img width="667" height="345" alt="demo1" src="https://github.com/user-attachments/assets/e58c761c-10fa-4c92-beb1-26d1a0cdc130" />


### Detection Workflow
<img width="667" height="345" alt="demo" src="https://github.com/user-attachments/assets/0f5f0dbb-987e-45ea-a7db-dd175df39109" />


### Sample Detections
<p align="">
  <img width="386" height="514" alt="image" src="https://github.com/user-attachments/assets/58713b00-d2a8-42a5-9d41-baabf353ab33" />
</p>
*Examples of AI-detected dental anomalies with bounding boxes.*

### Generated Report
<!-- Replace with PDF screenshot -->
<img width="518" height="336" alt="Picture1" src="https://github.com/user-attachments/assets/411fb00d-e5e7-40ba-8a76-db8636f6a1be" />

*Sample generated PDF report with findings table and clinical notes.*

---

## 🏗️ Architecture <a id="architecture"></a>

The application follows a **strict three-layer architecture** where each layer depends only on the layer below it, ensuring separation of concerns, testability, and maintainability.

```
┌─────────────────────────────────────────────────┐
│              main.py (Entry Point)              │
└─────────────────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────┐
│                  UI Layer                       │
│  ┌───────────────────────────────────────────┐  │
│  │  main_window.py  │  canvas.py  │ dialogs  │  │
│  │  widgets.py      │  styles.py             │  │
│  └───────────────────────────────────────────┘  │
│  Responsibility: User interaction, display      │
│  Dependencies: Services layer only              │
└─────────────────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────┐
│              Services Layer                     │
│  ┌───────────────────────────────────────────┐  │
│  │  case_service.py   — Patient/Case workflows│  │
│  │  detection_service — Model load/inference  │  │
│  │  report_service    — PDF generation        │  │
│  │  export_service    — CSV/Excel export      │  │
│  └───────────────────────────────────────────┘  │
│  Responsibility: Business logic orchestration   │
│  Dependencies: Data layer + filesystem          │
└─────────────────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────┐
│               Data Layer                        │
│  ┌───────────────────────────────────────────┐  │
│  │  database.py  — SQLite repository (CRUD)  │  │
│  └───────────────────────────────────────────┘  │
│  Responsibility: Database operations only       │
│  Dependencies: SQLite3 (no Qt, no filesystem)   │
└─────────────────────────────────────────────────┘
                        │
                  ┌──────────┐
                  │  SQLite  │
                  │ Database │
                  └──────────┘
```

### Layer Responsibilities

#### 1. **Data Layer** (`app/data/`)
- **Pure repository pattern**: Zero UI dependencies, no file I/O beyond the SQLite file.
- **Schema management**: Creates tables, enforces foreign key constraints, provides CRUD methods.
- **Testability**: Can be unit-tested independently without launching the GUI.

#### 2. **Services Layer** (`app/services/`)
- **Business logic orchestration**: Coordinates database operations, file management, and model execution.
- **Key modules**:
  - `case_service.py`: Atomic workflows for saving/deleting cases (DB write + image copy/delete).
  - `detection_service.py`: Asynchronous model loading and inference using QThread workers.
  - `report_service.py`: PDF generation with ReportLab.
  - `export_service.py`: Framework-agnostic CSV/Excel export.
- **Isolation**: Services talk to the data layer via `database.py` methods; no direct SQL queries in services.

#### 3. **UI Layer** (`app/ui/`)
- **Presentation only**: Renders widgets, handles user input, displays results.
- **Zero business logic**: Never touches SQLite, filesystem, or YOLO directly—delegates all operations to services.
- **Key components**:
  - `main_window.py`: Main application window orchestrating all UI elements.
  - `canvas.py`: Custom `ImageCanvas` widget for image display, bounding box drawing, and hit-testing.
  - `dialogs.py`: Modal dialogs for patient intake, adding/editing findings, and about info.
  - `widgets.py`: Reusable UI components (e.g., hover menu buttons).
  - `styles.py`: Centralized application stylesheet.

### Design Benefits

- **Replaceability**: Swap the UI (e.g., build a CLI or web interface) without touching business logic.
- **Testability**: Each layer can be tested in isolation.
- **Maintainability**: Clear boundaries reduce coupling and make debugging straightforward.
- **Scalability**: Easy to extend (e.g., add new export formats by adding a service module).

---

## 📈 Model Performance

The detection model is a **YOLOv8** variant enhanced with **channel and spatial attention blocks** to improve feature separation in complex dental panoramic images. Trained on a public datasets of **24,000+ OPG images** from Kaggle,TCIA,private datasets. the model balances speed and accuracy for real-time clinical use — exact benchmark metrics are pending publication.

### Detection Metrics
<!-- Replace with precision/recall/mAP charts -->
<p align="center">
<img width="499" height="299" alt="Picture2" src="https://github.com/user-attachments/assets/d1bec738-ae08-48d8-9866-e01592d23071" />
<img width="490" height="282" alt="Picture3" src="https://github.com/user-attachments/assets/55f472b9-df9a-4bc5-a57b-1c4b0f7c1d7b" />
</p>
*Precision-Recall curve and confusion matrix on validation set.*

### Key Characteristics
- **Lightweight**: Optimized for inference on standard CPUs (no GPU required).
- **Fast Inference**: Processes a typical OPG image in under 1 second.
- **31 Anomaly Classes**: Covers a wide range of dental conditions detectable in panoramic radiographs.
- **Attention Mechanism**: Helps the model focus on fine dental structures amidst overlapping anatomical noise.

> **Note**: The model is intended as a **computer-aided detection (CAD) tool** to assist dental professionals, not as a standalone diagnostic system. Always validate findings clinically.

---

## 🚀 Installation


### Alternative: Windows Portable Build

For Windows users who don't want to set up a Python environment, a portable build (`DentaView.exe`) is available as a Release asset on the project's GitHub Releases page. It's built with PyInstaller in `onedir` mode and ships with all runtime dependencies bundled in a `_internal` folder alongside the executable — just download it, extract, and run.

> Place `best.pt` (trained model weights) in the location expected by the app before running, if it isn't already bundled with the release.
---
## Standard Installation
### Prerequisites

- **Python 3.8+** (tested on 3.11)
- **pip** package manager
- **Virtual environment** (recommended)

### Step 1: Clone the Repository

```bash
git clone https://github.com/mahdiahmadii/DentalView.git
cd DentalView
```

### Step 2: Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Key dependencies** (see `requirements.txt` for full list):
- `PySide6` — Qt6 bindings for Python
- `ultralytics` — YOLOv8 framework
- `torch` — PyTorch deep learning library
- `opencv-python` — Image processing
- `Pillow` — Image handling
- `reportlab` — PDF report generation
- `openpyxl` — Excel export support

### Step 4: Model Weights

`best.pt` (the trained model weights) is included in the repository at:

```
DentalView/
└── assets/
    └── best.pt  # Trained YOLOv8 model weights
```

This path is resolved relative to `main.py`, so if `assets/best.pt` is present it loads automatically on startup — no manual step is required. You can still download or train your own weights and place them at the same path, or load a different weights file at any time via **Toolbar → Load Model**.

### Step 5: Run the Application

```bash
python main.py
```

The application will:
1. Create the `dental_data/` directory structure if it doesn't exist.
2. Initialize the SQLite database (`dental_records.db`).
3. Launch the main GUI window.


---

## 📖 Usage

### 1. Add a Patient

1. Click the **"+ Patient"** button in the sidebar.
2. Fill in patient details (name, ID, date of birth, phone, notes).
3. Click **Save**.

### 2. Load an OPG Image

1. Select a patient from the sidebar.
2. Click **"Open Image"** in the toolbar.
3. Choose an OPG X-ray file (supported formats: JPEG, PNG, BMP, TIFF).

### 3. Run AI Detection

1. With an image loaded, click **"Detect"** in the toolbar.
2. The model will run inference asynchronously (progress indicator shown).
3. Detected anomalies appear as bounding boxes on the image canvas.
4. The detection panel on the right lists all findings with confidence scores.

### 4. Add Manual Findings

1. Click **"Add Finding"** in the toolbar or right-click on the image canvas.
2. Draw a bounding box around the anomaly.
3. Enter the anomaly class name and optional notes.
4. Click **Save**.

### 5. Edit or Delete Findings

- **Edit**: Double-click a finding in the detection panel or click the **Edit** icon.
- **Delete**: Select a finding and click the **Delete** icon.

### 6. Adjust Confidence Threshold

- Use the **Confidence Slider** to filter AI detections by confidence level.
- Only findings above the threshold will be displayed and saved.

### 7. Save the Case

1. Click **"Save Case"** in the toolbar.
2. Enter a case label (e.g., "Annual Checkup 2026").
3. Optionally add a clinical summary.
4. The annotated image and findings are saved to the database.

### 8. Generate a PDF Report

1. With a saved case selected, click **"Export PDF"** in the toolbar.
2. Choose the destination folder.
3. A comprehensive medical report (image + findings table + notes) is generated.

### 9. Export to CSV/Excel

- Click **"Export"** → **"Export to CSV/Excel"** to export findings data for external analysis.

### 10. Case History & Deletion

- Access a patient's case history from the sidebar.
- Right-click on a case to **Delete** (removes DB entry and image files after confirmation).


---

## 🛠️ Technologies <a id="technologies"></a>

### Core Framework
- **[PySide6](https://pypi.org/project/PySide6/)** — Qt6 Python bindings for cross-platform GUI development.

### AI & Machine Learning
- **[YOLOv8](https://github.com/ultralytics/ultralytics)** (Ultralytics) — State-of-the-art object detection.
- **[PyTorch](https://pytorch.org/)** — Deep learning framework powering YOLO inference.

### Image Processing
- **[OpenCV](https://opencv.org/)** — Image manipulation and preprocessing.
- **[Pillow](https://pillow.readthedocs.io/)** — Python Imaging Library for I/O and transforms.

### Database
- **[SQLite3](https://www.sqlite.org/)** — Embedded relational database for local storage.

### Reporting & Export
- **[ReportLab](https://www.reportlab.com/)** — PDF generation with custom layouts and tables.
- **[openpyxl](https://openpyxl.readthedocs.io/)** — Excel (.xlsx) file read/write support.

### Utilities
- **[NumPy](https://numpy.org/)** — Numerical operations and array handling.

---

## 📂 Project Structure

```
DentalView/
├── main.py                     # Application entry point
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation
│
├── app/
│   ├── __init__.py
│   ├── config.py               # Paths, color palette, app metadata
│   │
│   ├── data/                   # Data layer (repository pattern)
│   │   ├── __init__.py
│   │   └── database.py         # SQLite schema + CRUD operations
│   │
│   ├── services/               # Business logic layer
│   │   ├── __init__.py
│   │   ├── case_service.py     # Patient/Case workflows
│   │   ├── detection_service.py # Model loading & inference (async)
│   │   ├── report_service.py   # PDF report generation
│   │   └── export_service.py   # CSV/Excel export
│   │
│   ├── ui/                     # User interface layer
│   │   ├── __init__.py
│   │   ├── main_window.py      # Main application window
│   │   ├── canvas.py           # Interactive image canvas
│   │   ├── dialogs.py          # Modal dialogs (patient, findings)
│   │   ├── widgets.py          # Custom Qt widgets
│   │   └── styles.py           # Application stylesheet
│   │
│   └── utils/                  # Framework-agnostic helpers
│       ├── __init__.py
│       └── helpers.py          # Color utils, filename generators
│
├── assets/
│   └── best.pt                 # YOLOv8 trained model weights
│
└── dental_data/                # Runtime data directory (auto-created)
    ├── dental_records.db       # SQLite database
    └── images/                 # Stored patient images
```

---

## 📦 Releasing a Windows Build

The portable Windows package is built with PyInstaller:

```bash
pyinstaller DentaView.spec
```

The output in `dist/DentaView/` contains `DentaView.exe` and a `_internal/` folder with all bundled dependencies. Compress the entire `dist/DentaView/` folder into a ZIP (e.g. `DentaView-v1.0.3-win64.zip`) and upload it as a GitHub Release asset.

> **Note**: With Ultralytics, PyTorch, and PySide6 bundled, the `_internal/` folder is large (approximately 2 GB). GitHub Release assets support files up to 2 GB — verify your specific build size before uploading.

---

## 🤝 Contributing

Contributions are welcome! Whether you're fixing bugs, improving documentation, or proposing new features, your input is valued.

### How to Contribute

1. **Fork the repository** on GitHub.
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Commit your changes**: `git commit -m "Add your feature description"`
4. **Push to your fork**: `git push origin feature/your-feature-name`
5. **Open a Pull Request** with a clear description of your changes.

### Development Guidelines

- Follow **PEP 8** style guidelines for Python code.
- Add **docstrings** to new functions and classes.
- Write **unit tests** for new features (place in `tests/` directory).
- Ensure the layered architecture is respected (no cross-layer violations).
- Test on multiple platforms if possible (Windows, macOS, Linux).

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Model Framework**: Built with [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics).
- **Inspiration**: Developed as a preliminary prototype to assess user acceptance in dental
  clinics and explore doctor–AI collaboration in diagnostic workflows.

---

## 📞 Contact

For questions, suggestions, or collaboration inquiries, feel free to reach out:

- **GitHub Issues**: [Open an issue](https://github.com/mahdiahmadii/DentalView/issues)
- **linkedin**: [mahdiahmadi](https://www.linkedin.com/in/mahdi-ahmadii/)

---

<p align="center">
  <strong>Built with ❤️ for dental professionals</strong>
</p>
