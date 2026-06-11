# OpenBioOps: A Complete Guide for Students

**Welcome!** This guide will teach you everything you need to know about OpenBioOps, a professional-grade bioinformatics platform. Don't worry if you're new to enterprise software - we'll explain every concept from the ground up.

**What you'll learn:**
- What this platform does and why it matters
- How modern web applications work
- What each technology does and why we use it
- How all the pieces fit together
- How to read and understand the code

**Time to read**: ~2 hours
**Prerequisites**: Basic programming (variables, functions, loops)

---

## Table of Contents

1. [What is OpenBioOps?](#what-is-openbioops)
2. [The Big Picture: How Modern Applications Work](#the-big-picture)
3. [Understanding the Tech Stack](#understanding-the-tech-stack)
4. [Architecture: How the Pieces Connect](#architecture)
5. [Following the Data: A Complete Journey](#following-the-data)
6. [Deep Dive: The Backend (API)](#deep-dive-backend)
7. [Deep Dive: The Database](#deep-dive-database)
8. [Deep Dive: Machine Learning](#deep-dive-ml)
9. [Deep Dive: The Frontend](#deep-dive-frontend)
10. [Deep Dive: DevOps & Deployment](#deep-dive-devops)
11. [Reading the Code: A Guided Tour](#reading-the-code)
12. [Common Patterns You'll See](#common-patterns)
13. [How to Get Started](#getting-started)
14. [Glossary of Terms](#glossary)

---

## What is OpenBioOps?

### The Simple Explanation

Imagine you're a scientist studying cells. You have a machine that can measure which genes are active in thousands of individual cells. This machine produces millions of data points. OpenBioOps helps you:

1. **Store** all that data
2. **Process** it to find patterns
3. **Visualize** it so humans can understand it
4. **Search** for similar experiments
5. **Share** results with other scientists

### The Technical Explanation

OpenBioOps is a **full-stack bioinformatics platform** for single-cell RNA sequencing (scRNA-seq) analysis. It:

- Ingests raw count matrices (how many times each gene appears in each cell)
- Processes them through quality control and feature extraction
- Uses machine learning to create "embeddings" (mathematical representations) of experiments
- Provides an API for searching, visualization, and analysis
- Includes a web dashboard for interactive exploration

### Why This Matters

**In biology:** Single-cell RNA sequencing helps us understand diseases at the cellular level. For example, understanding which cells in a tumor are different from healthy cells.

**In software:** This project demonstrates how to build a real production system with databases, APIs, machine learning, cloud deployment, and more - all the skills needed in industry.

---

## The Big Picture: How Modern Applications Work

Before we dive into specifics, let's understand how modern web applications are structured.

### The Client-Server Model

```
┌─────────────┐                          ┌─────────────┐
│   Your Web  │ ←-- HTTP Requests --→    │   Server    │
│   Browser   │     (over internet)      │  (Backend)  │
│  (Client)   │                          │             │
└─────────────┘                          └─────────────┘
      ↑                                         ↓
      │                                         │
   Displays                                 Talks to
   web pages                                   ↓
                                         ┌─────────────┐
                                         │  Database   │
                                         │  (Storage)  │
                                         └─────────────┘
```

**Client**: The web browser on your computer. It shows web pages and sends requests.

**Server**: A computer somewhere else that receives requests and sends back data.

**Database**: A specialized program for storing and retrieving data.

### Real-World Analogy

Think of it like a restaurant:

- **Client (Browser)**: You, the customer
- **Server (Backend)**: The waiter who takes your order
- **Database**: The kitchen where food (data) is stored and prepared

When you click a button on a website, you're like a customer ordering food. The request goes to the server (waiter), which gets data from the database (kitchen) and brings it back to you.

### The Three-Tier Architecture

OpenBioOps uses a **three-tier architecture**:

```
Tier 1: Presentation Layer (Frontend)
  ↓
Tier 2: Application Layer (Backend API)
  ↓
Tier 3: Data Layer (Database)
```

**Why separate these?**

1. **Specialization**: Different technologies are good at different things
2. **Scalability**: You can add more servers if one layer gets overloaded
3. **Security**: Sensitive data stays in protected layers
4. **Team organization**: Frontend developers and backend developers can work independently

---

## Understanding the Tech Stack

A "tech stack" is the collection of technologies used to build an application. Let's understand each piece.

### Frontend Technologies

**React** (JavaScript library)

```
What it does: Builds interactive user interfaces
Think of it like: LEGO blocks for websites

Example:
┌──────────────────────────────┐
│  [Button] Click Me           │  ← A React "component"
└──────────────────────────────┘

When clicked, it can update the page without reloading.
```

**Why React?**
- Makes complex interfaces manageable by breaking them into small pieces (components)
- Automatically updates the page when data changes
- Huge ecosystem of libraries and tools

**Real code example:**
```javascript
// A simple React component
function WelcomeMessage() {
  return <h1>Welcome to OpenBioOps!</h1>;
}

// A more complex component with state
function Counter() {
  const [count, setCount] = useState(0);

  return (
    <div>
      <p>Count: {count}</p>
      <button onClick={() => setCount(count + 1)}>
        Increment
      </button>
    </div>
  );
}
```

### Backend Technologies

**Python** (Programming language)

```
What it does: General-purpose programming language
Why we use it: Excellent for data science and scientific computing
Popular in: Machine learning, data analysis, automation
```

**FastAPI** (Web framework)

```
What it does: Makes it easy to build APIs (Application Programming Interfaces)
Think of it like: A receptionist that routes requests to the right place

Example API endpoint:
  You send: GET /v1/runs/123
  You get back: {id: "123", name: "Experiment A", ...}
```

**Why FastAPI?**
- Fast to write (hence the name)
- Automatically generates documentation
- Built-in validation (checks that data is correct)
- Modern Python features

**Real code example:**
```python
from fastapi import FastAPI

app = FastAPI()

# Define an endpoint
@app.get("/hello/{name}")
def say_hello(name: str):
    return {"message": f"Hello, {name}!"}

# When someone visits /hello/Alice, they get:
# {"message": "Hello, Alice!"}
```

**SQLAlchemy** (Database library)

```
What it does: Lets Python code talk to databases
Think of it like: A translator between Python and SQL (database language)

Python code:          SQLAlchemy          Database
 runs = query()  ←→   translates   ←→   SELECT * FROM runs
```

**Why SQLAlchemy?**
- You write Python instead of SQL
- Protects against SQL injection attacks
- Works with many different databases

**Real code example:**
```python
from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import Session

# Define a table structure
class Run(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    name = Column(String)
    status = Column(String)

# Query the database
def get_all_runs(db: Session):
    return db.query(Run).all()

# This is easier than writing:
# "SELECT id, name, status FROM runs"
```

### Machine Learning Technologies

**PyTorch** (ML framework)

```
What it does: Library for building neural networks (AI models)
Think of it like: A toolkit for teaching computers to recognize patterns

Example use:
- Input: Gene expression data from 10,000 cells
- Output: Which cell type each cell is (T cell, B cell, etc.)
```

**Why PyTorch?**
- Industry standard for research
- Flexible and powerful
- Great debugging (easier to find mistakes)

**scanpy** (Bioinformatics library)

```
What it does: Processes single-cell RNA sequencing data
Think of it like: Microsoft Excel, but for millions of cells

What it can do:
- Filter out low-quality cells
- Normalize data (make it comparable)
- Find patterns and clusters
```

**MLflow** (ML lifecycle management)

```
What it does: Tracks machine learning experiments
Think of it like: A lab notebook for ML experiments

It records:
- What parameters you used
- How well the model performed
- Which version of the model is in production
```

### Database Technology

**PostgreSQL** (Database)

```
What it does: Stores structured data in tables
Think of it like: Excel spreadsheets, but much more powerful

Example table (runs):
┌──────────┬─────────────┬──────────┐
│ id       │ name        │ status   │
├──────────┼─────────────┼──────────┤
│ abc-123  │ Experiment1 │ complete │
│ def-456  │ Experiment2 │ pending  │
└──────────┴─────────────┴──────────┘
```

**Why PostgreSQL?**
- Very reliable (won't lose your data)
- Handles millions of rows efficiently
- Supports complex queries
- Industry standard

### Infrastructure Technologies

**Docker** (Containerization)

```
What it does: Packages applications with all their dependencies
Think of it like: A shipping container for software

Problem: "It works on my computer but not yours"
Solution: Put your code + all dependencies in a Docker container

┌─────────────────────────────┐
│  Docker Container           │
│  ┌─────────────────────┐    │
│  │ Your Application    │    │
│  ├─────────────────────┤    │
│  │ Python 3.11         │    │
│  │ FastAPI             │    │
│  │ All libraries       │    │
│  └─────────────────────┘    │
└─────────────────────────────┘
    Runs the same everywhere!
```

**Kubernetes** (Container orchestration)

```
What it does: Manages many Docker containers across many servers
Think of it like: An orchestra conductor for containers

It handles:
- Starting and stopping containers
- Load balancing (distributing work)
- Automatic scaling (adding more containers when busy)
- Self-healing (restarting crashed containers)
```

**Terraform** (Infrastructure as Code)

```
What it does: Defines cloud infrastructure in code files
Think of it like: A blueprint for your cloud setup

Instead of clicking in AWS console:
1. Create a database
2. Create a server
3. Connect them

You write code:
terraform apply  ← Creates everything automatically
```

---

## Architecture: How the Pieces Connect

Now let's see how everything fits together in OpenBioOps.

### The Full System Diagram

```
                  Internet
                     │
                     ↓
        ┌────────────────────────┐
        │   Load Balancer        │  ← Distributes traffic
        └────────────┬───────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────↓─────┐          ┌─────↓────┐
    │  API     │          │  API     │  ← Multiple instances
    │  Server  │          │  Server  │     (auto-scaling)
    │  (8000)  │          │  (8000)  │
    └────┬─────┘          └─────┬────┘
         │                      │
         └──────────┬───────────┘
                    │
         ┏━━━━━━━━━━┷━━━━━━━━━━┓
         ┃                      ┃
    ┌────↓─────┐         ┌─────↓────┐
    │ Postgres │         │  Redis   │  ← Task queue
    │ Database │         │  Cache   │
    └──────────┘         └─────┬────┘
                               │
                        ┌──────↓───────┐
                        │ Celery       │  ← Background workers
                        │ Workers      │
                        └──────────────┘

    ┌────────────┐      ┌──────────────┐
    │  MLflow    │      │  ML Models   │  ← Experiment tracking
    │  Server    │      │  & Artifacts │
    │  (5000)    │      └──────────────┘
    └────────────┘
```

### Understanding Each Component

**Load Balancer**
- Receives all incoming traffic
- Distributes requests across multiple API servers
- If one server crashes, sends traffic to others

**API Servers**
- Handle HTTP requests (GET, POST, etc.)
- Validate input data
- Query the database
- Return responses
- Can scale to many copies

**PostgreSQL Database**
- Stores metadata about experiments
- Example: run ID, name, creation date, QC status
- Fast queries with indexes

**Redis Cache**
- In-memory data store (very fast)
- Used for task queue
- Stores temporary data

**Celery Workers**
- Process long-running tasks in the background
- Example: Processing a new dataset (takes 30+ seconds)
- Prevents API from getting blocked

**MLflow Server**
- Tracks ML experiments
- Stores model versions
- Web UI for viewing experiment history

---

## Following the Data: A Complete Journey

Let's follow a piece of biological data from start to finish.

### Step 1: Scientist Uploads Data

```
Scientist has raw data:
  ┌─────────────────────┐
  │ genes.tsv           │  ← File with gene names
  │ barcodes.tsv        │  ← File with cell IDs
  │ matrix.mtx          │  ← File with counts
  └─────────────────────┘

These files contain:
- 2,638 cells
- 32,738 genes
- ~8 million count values (how many times each gene appears in each cell)
```

**What happens:**
```python
# Scientist clicks "Upload" button in web interface
# React sends POST request to API

POST /v1/runs
{
  "name": "PBMC_3k_experiment",
  "raw_data_path": "s3://bucket/pbmc3k/"
}
```

### Step 2: API Receives Request

**Backend code (simplified):**
```python
@router.post("/v1/runs")
def create_run(payload: CreateRunRequest, db: Session):
    # 1. Create a unique ID
    run_id = str(uuid.uuid4())  # e.g., "a1b2c3d4-..."

    # 2. Save to database
    run = RunModel(
        id=run_id,
        name=payload.name,
        qc_status="processing"
    )
    db.add(run)
    db.commit()

    # 3. Queue background processing task
    extract_features_task.apply_async(
        args=(run_id, payload.raw_data_path)
    )

    # 4. Return immediately (don't wait for processing)
    return {"run_id": run_id, "status": "processing"}
```

**Why this design?**
- User gets immediate response (not waiting 30 seconds)
- Processing happens in background
- User can check status later

### Step 3: Background Processing

**Celery worker picks up task:**
```python
@celery_app.task
def extract_features_task(run_id, raw_data_path, output_dir):
    # 1. Load raw count matrix
    adata = scanpy.read_10x_mtx(raw_data_path)
    # adata = AnnData object with 2638 cells × 32738 genes

    # 2. Quality control
    # Remove cells with too few genes (might be dead cells)
    scanpy.pp.filter_cells(adata, min_genes=200)

    # Remove genes detected in too few cells
    scanpy.pp.filter_genes(adata, min_cells=3)

    # Calculate mitochondrial percentage
    # (high MT% suggests dying cells)
    adata.var['mt'] = adata.var_names.str.startswith('MT-')
    scanpy.pp.calculate_qc_metrics(adata, qc_vars=['mt'])

    # Filter out low-quality cells
    adata = adata[adata.obs.pct_counts_mt < 20]

    # 3. Normalization
    # Makes gene counts comparable between cells
    scanpy.pp.normalize_total(adata, target_sum=1e4)
    scanpy.pp.log1p(adata)  # Log transformation

    # 4. Feature selection
    # Find highly variable genes (most informative)
    scanpy.pp.highly_variable_genes(adata, n_top_genes=2000)

    # 5. PCA (dimensionality reduction)
    # Reduce from 2000 genes to 50 principal components
    scanpy.tl.pca(adata, n_comps=50)

    # 6. Save features
    features_df = pd.DataFrame(adata.obsm['X_pca'])
    features_df.to_parquet(f"{output_dir}/{run_id}.parquet")

    # 7. Update database
    update_run_status(run_id, "complete")
```

**What just happened?**

- Loaded 2,638 cells × 32,738 genes = 85 million data points
- Filtered to 2,638 cells × 2,000 genes (removed noise)
- Compressed to 2,638 cells × 50 features (PCA)
- Saved processed features

**Data transformation:**
```
Original:        After QC:           After PCA:
85M numbers  →   5.3M numbers   →   132K numbers
(too big)        (still big)        (manageable!)
```

### Step 4: Machine Learning Inference

**User requests embedding:**
```
POST /v1/runs/{run_id}/compute_vector
```

**Backend code:**
```python
@router.post("/{run_id}/compute_vector")
def compute_vector_for_run(run_id: str, db: Session):
    # 1. Load features (2638 cells × 50 dimensions)
    feature_path = f"features/{run_id}.parquet"
    features = pd.read_parquet(feature_path)

    # 2. Run through ML model
    model = load_model()  # Neural network
    embeddings = model.predict(features)
    # embeddings = 2638 cells × 64 dimensions

    # 3. Average across all cells to get run-level vector
    run_vector = embeddings.mean(axis=0)
    # run_vector = 64 dimensions

    # 4. Store in search index
    similarity_index.add(run_id, run_vector)

    # 5. Save embeddings
    pd.DataFrame(embeddings).to_parquet(
        f"artifacts/{run_id}.parquet"
    )

    return {"run_id": run_id, "vector_len": 64}
```

**What's happening with the ML model?**

```
Input: [PC1, PC2, ..., PC50]  ← 50 numbers per cell
       ↓
Neural Network Layers:
       ↓
Output: [E1, E2, ..., E64]    ← 64 numbers per cell

The model learned to compress 50 → 64 in a way that
preserves biological similarity.
```

### Step 5: Similarity Search

**User searches for similar experiments:**
```
GET /v1/similarity/{run_id}?k=5
```

**Backend code:**
```python
@router.get("/similarity/{run_id}")
def find_similar_runs(run_id: str, k: int = 5):
    # 1. Get query vector
    query_vector = similarity_index.get_vector(run_id)
    # query_vector = [0.23, -0.45, 0.12, ...]  (64 numbers)

    # 2. Search FAISS index
    # FAISS finds most similar vectors using cosine similarity
    similar_ids, scores = similarity_index.search(query_vector, k=k)

    # 3. Load metadata from database
    runs = db.query(RunModel).filter(
        RunModel.id.in_(similar_ids)
    ).all()

    # 4. Combine and return
    results = [
        {
            "run_id": run.id,
            "name": run.name,
            "similarity": score
        }
        for run, score in zip(runs, scores)
    ]

    return results
```

**How similarity search works:**

```
Imagine each experiment as a point in 64-dimensional space.

Your experiment: (0.2, -0.4, 0.1, ..., 0.3)
                     ↓
                Find nearest neighbors
                     ↓
┌─────────────────────────────────────┐
│  3D visualization (actually 64D):  │
│                                     │
│         ●  ← Exp2 (score: 0.95)    │
│       ●    ← Your experiment        │
│         ●  ← Exp3 (score: 0.93)    │
│                                     │
│                                     │
│    ●  ← Exp4 (score: 0.76)         │
│                                     │
│                                     │
│                     ● ← Exp5        │
│                       (score: 0.42) │
└─────────────────────────────────────┘
```

### Step 6: Visualization

**User requests UMAP visualization:**
```
GET /v1/viz/{run_id}/umap
```

**Backend code:**
```python
@router.get("/viz/{run_id}/umap")
def get_umap_coordinates(run_id: str):
    # 1. Load embeddings (2638 cells × 64 dimensions)
    embeddings = load_embeddings(run_id)

    # 2. Check if UMAP already computed
    umap_path = f"artifacts/{run_id}_umap.parquet"
    if not umap_path.exists():
        # 3. Compute UMAP (dimensionality reduction)
        import umap
        reducer = umap.UMAP(n_components=2)
        coords = reducer.fit_transform(embeddings)
        # coords = 2638 cells × 2 dimensions (x, y)

        # 4. Cluster cells
        from sklearn.cluster import KMeans
        clusters = KMeans(n_clusters=8).fit_predict(embeddings)

        # 5. Save
        df = pd.DataFrame({
            'x': coords[:, 0],
            'y': coords[:, 1],
            'cluster': clusters
        })
        df.to_parquet(umap_path)

    # 6. Load and return
    df = pd.read_parquet(umap_path)
    return df.to_dict(orient='records')
```

**What UMAP does:**

```
High-dimensional data (64 dimensions):
Cell 1: [0.2, -0.4, 0.1, ..., 0.3]  ← Can't visualize
Cell 2: [0.3, -0.2, 0.2, ..., 0.1]
...

UMAP ↓ (dimensionality reduction)

2D coordinates (can plot!):
Cell 1: [2.3, 5.1]   ← Can draw on screen
Cell 2: [2.5, 5.3]
...

Result: A scatter plot where similar cells are close together
```

### Step 7: Frontend Display

**React component:**
```javascript
function UMAPPlot({ runId }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    // Fetch data from API
    fetch(`/v1/viz/${runId}/umap`)
      .then(res => res.json())
      .then(coords => setData(coords));
  }, [runId]);

  if (!data) return <div>Loading...</div>;

  return (
    <ScatterPlot
      data={data}
      xKey="x"
      yKey="y"
      colorKey="cluster"
      width={800}
      height={600}
    />
  );
}
```

**What the user sees:**

```
┌────────────────────────────────────────┐
│  PBMC 3k UMAP                          │
├────────────────────────────────────────┤
│                                        │
│    Red dots        ← T cells          │
│         ●●●●                           │
│       ●●●●●●                           │
│                                        │
│  Blue dots  ●●●● ← B cells            │
│            ●●●●●                       │
│                                        │
│              Green dots ← Monocytes    │
│                  ●●●●●                 │
│                 ●●●●                   │
│                                        │
└────────────────────────────────────────┘
```

---

## Deep Dive: The Backend (API)

Let's explore the API layer in detail.

### What is an API?

**API = Application Programming Interface**

An API is like a menu at a restaurant:
- Shows what you can order (available endpoints)
- Describes each dish (input parameters)
- Tells you what you get (response format)

**HTTP Methods** (like verbs):
- `GET` - Retrieve data (like reading a book)
- `POST` - Create new data (like writing a new book)
- `PUT` - Update existing data (like editing a book)
- `DELETE` - Remove data (like throwing away a book)

### REST API Principles

**REST = Representational State Transfer**

Rules for designing APIs:
1. **Resources** have URLs: `/v1/runs`, `/v1/runs/123`
2. **Use HTTP methods** appropriately: GET for read, POST for create
3. **Stateless**: Each request is independent (no memory between requests)
4. **Return standard formats**: JSON

**Example REST design:**
```
GET    /v1/runs           ← List all runs
POST   /v1/runs           ← Create a new run
GET    /v1/runs/123       ← Get details of run 123
PUT    /v1/runs/123       ← Update run 123
DELETE /v1/runs/123       ← Delete run 123
```

### API Structure in OpenBioOps

**File organization:**
```
services/api/app/
├── main.py                 ← Application entry point
├── config.py               ← Configuration settings
├── db.py                   ← Database models
├── auth.py                 ← Authentication logic
├── routers/
│   └── v1/
│       ├── runs.py         ← /v1/runs endpoints
│       ├── similarity.py   ← /v1/similarity endpoints
│       ├── viz.py          ← /v1/viz endpoints
│       ├── models.py       ← /v1/models endpoints
│       └── batch.py        ← /v1/batch endpoints
└── ml/
    ├── model_server.py     ← ML inference
    └── similarity.py       ← FAISS search index
```

### Anatomy of an Endpoint

Let's dissect a complete endpoint:

```python
from fastapi import APIRouter, HTTPException, Path, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Create a router (collection of related endpoints)
router = APIRouter()

# 1. DEFINE REQUEST/RESPONSE MODELS
class CreateRunRequest(BaseModel):
    """Defines what data the client must send"""
    name: str = Field(..., max_length=255)
    # ... = required field
    # max_length = validation rule

    metadata: dict | None = Field(None)
    # | None = optional field

class CreateRunResponse(BaseModel):
    """Defines what the server sends back"""
    run_id: str
    name: str

# 2. DEFINE ENDPOINT
@router.post(
    "",  # Empty string means /v1/runs (base path)
    response_model=CreateRunResponse,  # Expected response type
    summary="Create a new run",  # Shows in API docs
    status_code=201  # HTTP status code for "Created"
)
def create_run(
    # DEPENDENCY INJECTION (explained below)
    payload: CreateRunRequest = Body(...),  # Request body
    db: Session = Depends(get_db),  # Database connection
    user: str = Depends(verify_token),  # Authenticated user
):
    """
    Create a new bioinformatics run.

    This docstring appears in the API documentation.
    """

    # 3. BUSINESS LOGIC

    # Generate unique ID
    run_id = str(uuid.uuid4())

    # Create database object
    run = RunModel(
        id=run_id,
        name=payload.name,
        metadata_=json.dumps(payload.metadata or {}),
        qc_status="unknown"
    )

    # Save to database
    db.add(run)
    db.commit()
    db.refresh(run)  # Get updated data

    # 4. RETURN RESPONSE
    return CreateRunResponse(
        run_id=run.id,
        name=run.name
    )
```

**What happens when this endpoint is called:**

1. **Request arrives**: `POST /v1/runs` with JSON body
2. **Validation**: Pydantic checks data matches `CreateRunRequest`
3. **Authentication**: `verify_token` checks if user is logged in
4. **Database connection**: `get_db` provides a database session
5. **Business logic**: Create and save the run
6. **Response**: Return JSON matching `CreateRunResponse`

### Dependency Injection

**What is it?** A way to provide objects (dependencies) to functions without creating them inside.

**Without dependency injection:**
```python
def create_run(payload):
    db = Database()  # Create connection
    user = check_auth()  # Check authentication
    # ... business logic
    db.close()  # Clean up
```

**Problems:**
- Hard to test (can't replace real database with fake one)
- Repeated code (every function creates its own connection)
- Hard to manage resources (when to close connections?)

**With dependency injection:**
```python
def create_run(
    payload: CreateRunRequest,
    db: Session = Depends(get_db),  # FastAPI provides this
    user: str = Depends(verify_token)  # FastAPI provides this
):
    # Just use db and user - don't worry about creating/closing
    pass
```

**Benefits:**
- Easy to test (inject a fake database)
- Clean code (dependencies provided automatically)
- Automatic cleanup (FastAPI handles connection lifecycle)

### Error Handling

**How APIs communicate errors:**

```python
@router.get("/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    # Try to find the run
    run = db.query(RunModel).filter(RunModel.id == run_id).first()

    # If not found, return error
    if run is None:
        raise HTTPException(
            status_code=404,  # Standard "Not Found" code
            detail=f"Run {run_id} not found"
        )

    # If found, return it
    return run
```

**HTTP Status Codes** (standard across all web APIs):
- `200 OK` - Request succeeded
- `201 Created` - New resource created
- `400 Bad Request` - Client sent invalid data
- `401 Unauthorized` - Not logged in
- `403 Forbidden` - Logged in but not allowed
- `404 Not Found` - Resource doesn't exist
- `500 Internal Server Error` - Server bug

### Authentication

**How we verify users:**

```python
# 1. User logs in
@router.post("/auth/token")
def login(username: str, password: str):
    # Check credentials
    if not verify_password(username, password):
        raise HTTPException(status_code=401)

    # Create JWT token
    token = jwt.encode(
        {"sub": username, "exp": expiration_time},
        secret_key
    )

    return {"access_token": token}

# 2. User includes token in requests
# Authorization: Bearer eyJhbGc...

# 3. API verifies token
def verify_token(authorization: str = Header()):
    token = authorization.replace("Bearer ", "")

    try:
        payload = jwt.decode(token, secret_key)
        return payload["sub"]  # Return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
```

**JWT (JSON Web Token):**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyMTIzIiwiZXhwIjoxNjc4OTQ3MDAwfQ.Xq-O6KxpLH_3pD7R8TN2rFo4Z8kQ1Qn7Vz3K1jD8xE
│                                         │                                              │
│         Header                          │             Payload                          │    Signature
│   (algorithm & type)                    │      (username & expiration)                 │  (verify not tampered)
```

---

## Deep Dive: The Database

### What is a Database?

A database is like Excel, but:
- Handles millions of rows efficiently
- Multiple users can access simultaneously
- Enforces data rules (constraints)
- Provides ACID guarantees (explained below)

### SQL Basics

**SQL = Structured Query Language**

```sql
-- Create a table
CREATE TABLE runs (
    id VARCHAR PRIMARY KEY,
    name VARCHAR(255),
    status VARCHAR,
    created_at TIMESTAMP
);

-- Insert data
INSERT INTO runs (id, name, status, created_at)
VALUES ('abc-123', 'Experiment 1', 'complete', NOW());

-- Query data
SELECT id, name FROM runs WHERE status = 'complete';

-- Update data
UPDATE runs SET status = 'archived' WHERE id = 'abc-123';

-- Delete data
DELETE FROM runs WHERE status = 'archived';
```

### Database Schema in OpenBioOps

**Schema = structure of tables**

```
┌─────────────────────────────────────────────┐
│              runs table                     │
├───────────┬─────────┬─────────┬────────────┤
│ id (PK)   │ name    │ status  │ created_at │
├───────────┼─────────┼─────────┼────────────┤
│ abc-123   │ Exp 1   │complete │2024-01-15  │
│ def-456   │ Exp 2   │pending  │2024-01-16  │
└───────────┴─────────┴─────────┴────────────┘

┌─────────────────────────────────────────────────────────┐
│           prediction_logs table                         │
├────────┬────────┬────────┬───────────┬──────────────────┤
│ id (PK)│ run_id │ model  │prediction │ timestamp        │
├────────┼────────┼────────┼───────────┼──────────────────┤
│ 1      │abc-123 │ v2.0   │ [0.1...]  │2024-01-15 10:30  │
│ 2      │def-456 │ v2.0   │ [0.2...]  │2024-01-16 11:00  │
└────────┴────────┴────────┴───────────┴──────────────────┘
              ↑
              └─── Foreign key relationship
```

**Primary Key (PK)**: Unique identifier for each row
**Foreign Key (FK)**: Reference to another table

### ORM: Object-Relational Mapping

**Instead of writing SQL:**
```sql
SELECT * FROM runs WHERE status = 'complete';
```

**We write Python:**
```python
runs = db.query(Run).filter(Run.status == 'complete').all()
```

**How it works:**

```python
# 1. Define a model (Python class)
class RunModel(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    name = Column(String(255))
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# 2. Create (INSERT)
new_run = RunModel(id="abc-123", name="Exp 1", status="pending")
db.add(new_run)
db.commit()  # Save to database

# 3. Read (SELECT)
run = db.query(RunModel).filter(RunModel.id == "abc-123").first()
print(run.name)  # "Exp 1"

# 4. Update
run.status = "complete"
db.commit()

# 5. Delete
db.delete(run)
db.commit()
```

### Database Migrations

**Problem**: Database schema changes over time

```
Week 1: runs table has 3 columns
Week 5: Need to add 'priority' column
Week 10: Need to rename 'status' to 'qc_status'
```

**Solution**: Alembic (migration tool)

```python
# migrations/versions/001_add_priority.py
def upgrade():
    op.add_column('runs', sa.Column('priority', sa.Integer))

def downgrade():
    op.drop_column('runs', 'priority')
```

**Commands:**
```bash
# Create migration
alembic revision -m "Add priority column"

# Apply migrations
alembic upgrade head

# Rollback (undo)
alembic downgrade -1
```

### ACID Properties

**Why databases are reliable:**

**Atomicity**: All-or-nothing
```python
# Either both succeed or both fail
db.add(run1)
db.add(run2)
db.commit()  # If this fails, neither is saved
```

**Consistency**: Rules always enforced
```python
# Can't create run with duplicate ID (PRIMARY KEY constraint)
```

**Isolation**: Transactions don't interfere
```
User A: Reading runs       │  User B: Creating run
  SELECT * FROM runs        │    INSERT INTO runs
  ← Both operations work independently
```

**Durability**: Committed data survives crashes
```
db.commit()  ← Once this returns, data is safe even if server crashes
```

---

## Deep Dive: Machine Learning

### What is Machine Learning?

**Traditional programming:**
```
Input → Rules (written by programmer) → Output

Example:
Temperature in Celsius → multiply by 1.8 and add 32 → Fahrenheit
```

**Machine learning:**
```
Input + Desired Output → Learning Algorithm → Rules

Example:
Images of cats + Label "cat" → Training → Model that recognizes cats
```

### Our ML Task: Run Similarity

**Goal**: Find experiments with similar biology

**Approach**: Convert each experiment to a vector (list of numbers) such that similar experiments have similar vectors.

**Example:**
```
Experiment A (liver cells):    [0.2, 0.8, -0.1, ..., 0.4]
Experiment B (liver cells):    [0.3, 0.7, -0.2, ..., 0.5]  ← Similar!
Experiment C (brain cells):    [-0.9, 0.1, 0.8, ..., -0.3] ← Different
```

### Neural Networks Basics

**What is a neural network?**

Think of it like a complex mathematical function:
```
f(x) = output

Where f has millions of parameters that we "learn" from data
```

**Structure:**
```
Input Layer → Hidden Layers → Output Layer

Example: Recognize handwritten digits

Input: 784 numbers (28×28 pixel image)
  ↓
Hidden Layer 1: 128 neurons
  ↓
Hidden Layer 2: 64 neurons
  ↓
Output: 10 numbers (probability for digits 0-9)
```

**Neuron (building block):**
```python
def neuron(inputs, weights, bias):
    # 1. Weighted sum
    total = sum(x * w for x, w in zip(inputs, weights)) + bias

    # 2. Activation function (adds non-linearity)
    output = relu(total)  # relu(x) = max(0, x)

    return output
```

### Our Model: Contrastive Encoder

**Purpose**: Learn embeddings where similar cells are close together

**Architecture:**
```python
class ContrastiveEncoder(nn.Module):
    def __init__(self, input_dim=50, latent_dim=64):
        super().__init__()

        # Layer 1: 50 → 128
        self.fc1 = nn.Linear(input_dim, 128)
        self.bn1 = nn.BatchNorm1d(128)  # Normalization

        # Layer 2: 128 → 128
        self.fc2 = nn.Linear(128, 128)
        self.bn2 = nn.BatchNorm1d(128)

        # Layer 3: 128 → 64
        self.fc3 = nn.Linear(128, latent_dim)

        self.dropout = nn.Dropout(0.2)  # Regularization

    def forward(self, x):
        # Pass data through layers
        x = self.dropout(F.relu(self.bn1(self.fc1(x))))
        x = self.dropout(F.relu(self.bn2(self.fc2(x))))
        x = self.fc3(x)
        return x
```

**Visualizing data flow:**
```
Input: [PC1, PC2, ..., PC50]  (50 numbers)
  ↓
Layer 1: [N1, N2, ..., N128]  (128 neurons)
  ↓ ReLU activation
  ↓ Dropout (randomly zero some neurons)
  ↓
Layer 2: [N1, N2, ..., N128]  (128 neurons)
  ↓ ReLU activation
  ↓ Dropout
  ↓
Layer 3: [E1, E2, ..., E64]   (64 outputs)
  ↓
Output: Embedding vector
```

### Training Process

**Goal**: Adjust weights so similar cells get similar embeddings

**NT-Xent Loss** (Normalized Temperature-Scaled Cross Entropy):

```python
def nt_xent_loss(embeddings_i, embeddings_j, temperature=0.5):
    """
    embeddings_i: Batch of original cells
    embeddings_j: Batch of augmented cells (simulated dropout)

    Goal: Make embedding_i[k] similar to embedding_j[k] (same cell)
          Make embedding_i[k] different from all others
    """

    # 1. Compute similarity between all pairs
    similarity = cosine_similarity(embeddings_i, embeddings_j)
    # similarity[i,j] = how similar cell i and cell j are

    # 2. Apply temperature scaling
    similarity = similarity / temperature

    # 3. Cross-entropy loss
    # Encourages similarity[i,i] to be high
    # Encourages similarity[i,j] (j≠i) to be low
    loss = cross_entropy_loss(similarity, targets)

    return loss
```

**Training loop:**
```python
model = ContrastiveEncoder()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

for epoch in range(50):
    for batch in dataloader:
        # 1. Forward pass (get predictions)
        embeddings_1 = model(batch)

        # 2. Create augmented version (simulate dropout)
        augmented_batch = apply_dropout(batch, p=0.1)
        embeddings_2 = model(augmented_batch)

        # 3. Compute loss
        loss = nt_xent_loss(embeddings_1, embeddings_2)

        # 4. Backward pass (compute gradients)
        loss.backward()

        # 5. Update weights
        optimizer.step()
        optimizer.zero_grad()
```

**What's happening:**
1. Show model some data
2. Model makes predictions
3. Compare predictions to what we want (loss function)
4. Adjust weights to improve (optimization)
5. Repeat thousands of times

### FAISS: Fast Similarity Search

**Problem**: Given a vector, find the most similar vectors from 10,000+ stored vectors

**Naive approach** (too slow):
```python
def find_similar(query, all_vectors):
    similarities = []
    for vector in all_vectors:  # 10,000 iterations
        sim = cosine_similarity(query, vector)  # Expensive
        similarities.append(sim)
    return top_k(similarities, k=5)

# Time: O(n × d) where n=10,000, d=64
```

**FAISS approach** (fast):
```python
# 1. Build index (one-time setup)
index = faiss.IndexFlatIP(dimension=64)  # Inner product
index.add(all_vectors)  # Add all vectors

# 2. Search (fast!)
similarities, indices = index.search(query, k=5)
# Time: O(log n × d) - much faster!
```

**How FAISS achieves speed:**
- Optimized C++ implementation
- SIMD instructions (process multiple numbers simultaneously)
- Smart data structures (approximate nearest neighbors)

---

## Deep Dive: The Frontend

### What is React?

**React** = JavaScript library for building user interfaces

**Key concept: Components**

A component is a reusable piece of UI:
```javascript
// A simple component
function Button({ text, onClick }) {
  return (
    <button onClick={onClick}>
      {text}
    </button>
  );
}

// Use it
<Button text="Click Me" onClick={handleClick} />
```

**Component tree:**
```
<App>
  ├─ <Header />
  ├─ <Dashboard>
  │   ├─ <RunList />
  │   │   ├─ <RunItem />
  │   │   ├─ <RunItem />
  │   │   └─ <RunItem />
  │   └─ <Visualization>
  │       └─ <UMAPPlot />
  └─ <Footer />
```

### State Management

**State** = data that can change over time

```javascript
function Counter() {
  // useState hook: [value, setter function]
  const [count, setCount] = useState(0);

  return (
    <div>
      <p>Count: {count}</p>
      <button onClick={() => setCount(count + 1)}>
        Increment
      </button>
    </div>
  );
}
```

**When state changes, React re-renders the component:**
```
User clicks button
  ↓
setCount(count + 1) called
  ↓
count changes from 0 to 1
  ↓
React re-renders component
  ↓
User sees new count
```

### Fetching Data from API

```javascript
function RunList() {
  const [runs, setRuns] = useState([]);  // Empty initially
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // useEffect: Run code after component mounts
  useEffect(() => {
    // Fetch data from API
    fetch('/v1/runs')
      .then(response => {
        if (!response.ok) throw new Error('Failed to fetch');
        return response.json();
      })
      .then(data => {
        setRuns(data.runs);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);  // Empty array = run once on mount

  // Conditional rendering
  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <ul>
      {runs.map(run => (
        <li key={run.id}>{run.name}</li>
      ))}
    </ul>
  );
}
```

**Data flow:**
```
1. Component mounts → loading=true, runs=[]
2. useEffect runs → fetch('/v1/runs')
3. API responds → data arrives
4. setRuns(data.runs) → runs updated
5. setLoading(false) → loading=false
6. React re-renders → show runs list
```

### Component Lifecycle

```
Mount (component appears):
  ↓
constructor / useState
  ↓
render (initial)
  ↓
useEffect (after first render)
  ↓
Updates (state/props change):
  ↓
render (again)
  ↓
useEffect (if dependencies changed)
  ↓
Unmount (component disappears):
  ↓
cleanup (useEffect return function)
```

---

## Deep Dive: DevOps & Deployment

### What is DevOps?

**DevOps** = Development + Operations

The practice of automating and streamlining software delivery.

**Traditional approach:**
```
Developers write code → Throw over wall → Operations team deploys
  ↓                                              ↓
Fast changes                                   Slow, manual, error-prone
```

**DevOps approach:**
```
Developers write code → Automated testing → Automated deployment
  ↓                           ↓                      ↓
All automated         Catches bugs early      Fast, consistent
```

### Docker Containers

**Problem**: "It works on my machine!"

```
Developer's laptop:
- Python 3.11
- FastAPI 0.100
- Works perfectly!

Production server:
- Python 3.9
- FastAPI 0.95
- Everything breaks!
```

**Solution**: Docker containers

```dockerfile
# Dockerfile: Recipe for container
FROM python:3.11-slim

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . /app
WORKDIR /app

# Run application
CMD ["python", "main.py"]
```

**Build and run:**
```bash
# Build image
docker build -t openbioops-api .

# Run container
docker run -p 8000:8000 openbioops-api

# Now it works the same everywhere!
```

**Container vs VM:**
```
Virtual Machine:                Container:

┌──────────────────┐            ┌──────────────────┐
│  App A   App B   │            │  App A   App B   │
│  ┌───┐  ┌───┐   │            │  ┌───┐  ┌───┐   │
│  └───┘  └───┘   │            │  └───┘  └───┘   │
├──────────────────┤            ├──────────────────┤
│ Guest OS   Guest │            │  Docker Engine   │
│   OS             │            ├──────────────────┤
├──────────────────┤            │  Host OS         │
│  Hypervisor      │            └──────────────────┘
├──────────────────┤
│  Host OS         │            Lightweight!
└──────────────────┘            Fast startup!
                                Share OS kernel!
Heavy!
Slow startup!
```

### Docker Compose: Multiple Containers

**Problem**: Our app needs multiple services (API, database, Redis)

**docker-compose.yml:**
```yaml
services:
  api:
    build: ./services/api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://db:5432/openbioops
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=openbioops
      - POSTGRES_PASSWORD=secret
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  celery:
    build: ./services/api
    command: celery -A app.tasks worker
    depends_on:
      - redis
      - db

volumes:
  postgres_data:
```

**Start everything:**
```bash
docker-compose up

# Starts:
# - API on port 8000
# - PostgreSQL database
# - Redis cache
# - Celery workers
```

### Kubernetes: Container Orchestration

**Problem**: Need to run containers across many servers

**What Kubernetes does:**
1. **Scheduling**: Decides which server runs which container
2. **Load balancing**: Distributes traffic across containers
3. **Auto-scaling**: Adds more containers when traffic increases
4. **Self-healing**: Restarts crashed containers
5. **Rolling updates**: Deploy new versions without downtime

**Basic concepts:**

**Pod**: Smallest unit (one or more containers)
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: api-pod
spec:
  containers:
  - name: api
    image: openbioops-api:v1.0
    ports:
    - containerPort: 8000
```

**Deployment**: Manages multiple pods
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-deployment
spec:
  replicas: 3  # Run 3 copies
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: openbioops-api:v1.0
```

**Service**: Exposes pods to network
```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-service
spec:
  selector:
    app: api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer  # Get external IP
```

**Horizontal Pod Autoscaler**: Auto-scaling
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-deployment
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

**What happens:**
```
Low traffic:        High traffic:       Traffic drops:
2 pods running  →   20 pods running  →  2 pods running
                    (auto-scaled up)    (auto-scaled down)
```

### CI/CD Pipeline

**CI/CD** = Continuous Integration / Continuous Deployment

**Goal**: Automatically test and deploy code

**GitHub Actions workflow:**
```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: pytest

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Build Docker image
        run: docker build -t api:${{ github.sha }} .
      - name: Push to registry
        run: docker push api:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Kubernetes
        run: kubectl set image deployment/api api=api:${{ github.sha }}
```

**What happens when you push code:**
```
1. Git push main
     ↓
2. GitHub Actions triggered
     ↓
3. Run tests
     ↓ (if tests pass)
4. Build Docker image
     ↓
5. Push to container registry
     ↓
6. Deploy to staging
     ↓
7. Run integration tests
     ↓ (if tests pass)
8. Deploy to production
```

**Blue-Green Deployment:**
```
Old version (blue):     New version (green):
┌─────────────┐         ┌─────────────┐
│  API v1.0   │         │  API v2.0   │
│  3 pods     │         │  3 pods     │
└─────────────┘         └─────────────┘
       ↑                      ↓
       │                      │
  All traffic            No traffic (testing)
       │                      │
       └──────────┬───────────┘
                  │
         Switch traffic  ← Instant cutover
                  │
       ┌──────────┴───────────┐
       ↓                      ↑
┌─────────────┐         ┌─────────────┐
│  API v1.0   │         │  API v2.0   │
│  (delete)   │         │  3 pods     │
└─────────────┘         └─────────────┘
                           All traffic

If something breaks: switch back to blue (instant rollback)
```

### Infrastructure as Code (Terraform)

**Problem**: Manually clicking in AWS console is slow and error-prone

**Solution**: Define infrastructure in code

**Terraform example:**
```hcl
# VPC (Virtual Private Cloud)
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"

  tags = {
    Name = "openbioops-vpc"
  }
}

# Database
resource "aws_db_instance" "postgres" {
  engine         = "postgres"
  engine_version = "15.3"
  instance_class = "db.t3.medium"

  allocated_storage = 100
  storage_type      = "gp3"

  db_name  = "openbioops"
  username = var.db_username
  password = var.db_password

  multi_az = true  # High availability
}

# Kubernetes cluster
resource "aws_eks_cluster" "main" {
  name     = "openbioops-cluster"
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids = aws_subnet.private[*].id
  }
}
```

**Commands:**
```bash
# See what will be created
terraform plan

# Create everything
terraform apply

# Tear down everything
terraform destroy
```

**Benefits:**
1. **Reproducible**: Same code = same infrastructure
2. **Version controlled**: Track changes in Git
3. **Documented**: Code is documentation
4. **Testable**: Test infrastructure changes before applying

---

## Reading the Code: A Guided Tour

Let's walk through real code from the project.

### Example 1: Create Run Endpoint

**File**: `services/api/app/routers/v1/runs.py`

```python
@router.post("", response_model=CreateRunResponse)
def create_run(
    payload: CreateRunRequest = Body(...),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Create a new bioinformatics run."""

    # 1. Validate path if provided
    if payload.raw_data_path:
        validate_path_safe(payload.raw_data_path)

    # 2. Create database object
    run = RunModel(
        id=str(uuid.uuid4()),
        name=payload.name,
        metadata_=JSONField.dumps(payload.metadata),
        qc_status="unknown",
    )

    # 3. Save to database
    db.add(run)
    db.commit()
    db.refresh(run)

    # 4. Auto-generate features if raw data provided
    if payload.raw_data_path:
        extract_features_task.apply_async(
            args=(run.id, payload.raw_data_path)
        )
        run.qc_status = "processing"
        db.commit()

    # 5. Return response
    return CreateRunResponse(run_id=run.id, name=run.name)
```

**Reading guide:**

- `@router.post("")` - Decorator that registers this as a POST endpoint
- `payload: CreateRunRequest` - Input validation via Pydantic
- `db: Session = Depends(get_db)` - Dependency injection for database
- `user: str = Depends(verify_token)` - Requires authentication
- `validate_path_safe()` - Security check (prevent directory traversal)
- `uuid.uuid4()` - Generate unique ID
- `JSONField.dumps()` - Custom utility for JSON serialization
- `db.commit()` - Save changes to database
- `apply_async()` - Queue background task (Celery)

### Example 2: Similarity Search

**File**: `services/api/app/routers/v1/similarity.py`

```python
@router.get("/{run_id}")
def find_similar_runs(
    run_id: str = Path(...),
    k: int = Query(5, ge=1, le=100),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Find k most similar runs."""

    # 1. Validate UUID
    validate_uuid(run_id)

    # 2. Get similarity index
    sim_index = dependencies.get_sim_index()

    # 3. Check if vector exists
    if run_id not in sim_index.vectors:
        raise HTTPException(
            status_code=404,
            detail="No vector computed for this run"
        )

    # 4. Search
    similar_ids, scores = sim_index.search(run_id, k=k)

    # 5. Load metadata from database
    runs = db.query(RunModel).filter(
        RunModel.id.in_(similar_ids)
    ).all()

    # 6. Build response
    results = [
        {
            "run_id": run.id,
            "name": run.name,
            "similarity": float(score)
        }
        for run, score in zip(runs, scores)
    ]

    return {"query_run_id": run_id, "results": results}
```

**Reading guide:**

- `Path(...)` - Extract run_id from URL path
- `Query(5, ge=1, le=100)` - Extract k from query string, validate 1-100
- `validate_uuid()` - Security check (prevent injection)
- `dependencies.get_sim_index()` - Get FAISS search index
- `sim_index.search()` - Fast nearest neighbor search
- `filter(RunModel.id.in_(similar_ids))` - SQL IN query
- List comprehension - Build response list
- `float(score)` - Convert numpy float to Python float (JSON serializable)

### Example 3: Background Task

**File**: `services/api/app/tasks.py`

```python
@celery_app.task(bind=True, max_retries=3)
def extract_features_task(self, run_id, raw_data_path, output_dir):
    """Extract features from raw scRNA-seq data."""

    try:
        # 1. Load data
        adata = scanpy.read_10x_mtx(raw_data_path)

        # 2. Quality control
        scanpy.pp.filter_cells(adata, min_genes=200)
        scanpy.pp.filter_genes(adata, min_cells=3)

        # Calculate QC metrics
        adata.var['mt'] = adata.var_names.str.startswith('MT-')
        scanpy.pp.calculate_qc_metrics(adata, qc_vars=['mt'])

        # Filter by QC
        adata = adata[adata.obs.pct_counts_mt < 20]
        adata = adata[adata.obs.n_genes_by_counts < 7000]

        # 3. Normalization
        scanpy.pp.normalize_total(adata, target_sum=1e4)
        scanpy.pp.log1p(adata)

        # 4. Feature selection
        scanpy.pp.highly_variable_genes(adata, n_top_genes=2000)

        # 5. PCA
        scanpy.tl.pca(adata, n_comps=50)

        # 6. Save features
        features_df = pd.DataFrame(
            adata.obsm['X_pca'],
            columns=[f'PC{i+1}' for i in range(50)]
        )
        output_path = Path(output_dir) / f"{run_id}.parquet"
        features_df.to_parquet(output_path)

        # 7. Update database
        update_run_status(run_id, "complete")

    except Exception as exc:
        # Retry on failure
        update_run_status(run_id, "failed")
        raise self.retry(exc=exc, countdown=60)  # Wait 1 min
```

**Reading guide:**

- `@celery_app.task(bind=True)` - Celery task decorator
- `bind=True` - Gives access to `self` (task instance)
- `max_retries=3` - Retry up to 3 times on failure
- `scanpy.pp.*` - scanpy preprocessing functions
- `adata.obsm['X_pca']` - PCA results (observations × PCA components)
- `to_parquet()` - Save as compressed columnar format
- `self.retry()` - Retry task if it fails
- `countdown=60` - Wait 60 seconds before retry

### Example 4: Database Model

**File**: `services/api/app/db.py`

```python
class RunModel(Base):
    """Database model for bioinformatics runs."""

    __tablename__ = "runs"

    # Columns
    id = Column(String, primary_key=True)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    qc_status = Column(String, default="unknown")
    metadata_ = Column(Text, default="{}")
    qc_metrics_ = Column(Text, default="{}")

    # Computed properties
    @property
    def metadata(self) -> dict:
        """Deserialize metadata JSON."""
        return json.loads(self.metadata_ or "{}")

    @metadata.setter
    def metadata(self, value: dict):
        """Serialize metadata to JSON."""
        self.metadata_ = json.dumps(value or {})

    def __repr__(self):
        return f"<Run(id={self.id}, name={self.name})>"
```

**Reading guide:**

- `Base` - SQLAlchemy base class (all models inherit from this)
- `__tablename__` - Name of database table
- `Column(String, primary_key=True)` - Define column type and constraints
- `default=datetime.utcnow` - Automatic timestamp
- `@property` - Make method accessible like attribute: `run.metadata`
- `@metadata.setter` - Allow setting: `run.metadata = {...}`
- `__repr__` - String representation for debugging

### Example 5: React Component

**File**: `services/dashboard/src/components/RunList.jsx`

```javascript
function RunList() {
  // State
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch data on mount
  useEffect(() => {
    async function fetchRuns() {
      try {
        const response = await fetch('/v1/runs');
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        setRuns(data.runs);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    fetchRuns();
  }, []);  // Empty deps = run once

  // Render
  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div className="run-list">
      <h2>Experiments ({runs.length})</h2>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {runs.map(run => (
            <tr key={run.id}>
              <td>{run.name}</td>
              <td>
                <StatusBadge status={run.qc_status} />
              </td>
              <td>{new Date(run.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

**Reading guide:**

- `useState([])` - Create state variable, initial value = empty array
- `useEffect()` - Run code after component renders
- `async/await` - Modern JavaScript for async operations
- `fetch()` - Make HTTP request
- `response.json()` - Parse JSON response body
- `try/catch/finally` - Error handling
- `runs.map()` - Transform array to JSX elements
- `key={run.id}` - Required for React lists (helps with updates)
- JSX - HTML-like syntax in JavaScript

---

## Common Patterns You'll See

### Pattern 1: Error Handling

```python
def get_run(run_id: str, db: Session):
    # Validate input
    if not is_valid_uuid(run_id):
        raise HTTPException(status_code=400, detail="Invalid UUID")

    # Query database
    run = db.query(RunModel).filter(RunModel.id == run_id).first()

    # Check if found
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    return run
```

### Pattern 2: Pagination

```python
@router.get("/runs")
def list_runs(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    # Count total
    total = db.query(RunModel).count()

    # Get page
    runs = (
        db.query(RunModel)
        .order_by(RunModel.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "runs": runs
    }
```

### Pattern 3: Try-Except-Finally

```python
def process_file(file_path):
    file_handle = None
    try:
        # Open file
        file_handle = open(file_path, 'r')

        # Process
        data = file_handle.read()
        result = analyze(data)

        return result

    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None

    except Exception as e:
        print(f"Unexpected error: {e}")
        raise

    finally:
        # Always runs (cleanup)
        if file_handle:
            file_handle.close()
```

### Pattern 4: Context Managers

```python
# Better way (automatic cleanup)
def process_file(file_path):
    with open(file_path, 'r') as f:
        data = f.read()
        return analyze(data)
    # File automatically closed here

# Database sessions
def get_runs():
    with Session() as db:
        runs = db.query(RunModel).all()
        return runs
    # Session automatically closed
```

### Pattern 5: List Comprehensions

```python
# Long way
results = []
for run in runs:
    if run.status == "complete":
        results.append(run.name)

# Short way (list comprehension)
results = [run.name for run in runs if run.status == "complete"]

# With transformation
squared = [x**2 for x in range(10)]
# [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
```

### Pattern 6: Async/Await (JavaScript)

```javascript
// Sequential (slow)
const data1 = await fetch('/api/1').then(r => r.json());
const data2 = await fetch('/api/2').then(r => r.json());
// Total time: time1 + time2

// Parallel (fast)
const [data1, data2] = await Promise.all([
  fetch('/api/1').then(r => r.json()),
  fetch('/api/2').then(r => r.json())
]);
// Total time: max(time1, time2)
```

---

## Getting Started

### Prerequisites

**Install required software:**

1. **Git** - Version control
   ```bash
   # Windows: Download from git-scm.com
   # Mac: brew install git
   # Linux: sudo apt install git
   ```

2. **Docker** - Container platform
   ```bash
   # Download from docker.com
   # Verify: docker --version
   ```

3. **Python 3.11** (for local development)
   ```bash
   # Download from python.org
   # Verify: python --version
   ```

4. **Node.js** (for frontend development)
   ```bash
   # Download from nodejs.org
   # Verify: node --version
   ```

### Clone and Run

```bash
# 1. Clone repository
git clone https://github.com/SethJoslin/BioTechDemo
cd BioTechDemo

# 2. Start all services
docker-compose up

# Wait for services to start...
# API: http://localhost:8000
# Dashboard: http://localhost:3000
# MLflow: http://localhost:5000
```

### Explore the API

```bash
# 1. Get an auth token
curl -X POST http://localhost:8000/v1/auth/token /
  -H "Content-Type: application/json" /
  -d '{"username": "demo"}'

# Response: {"access_token": "eyJ..."}

# 2. List runs
curl http://localhost:8000/v1/runs /
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. Create a run
curl -X POST http://localhost:8000/v1/runs /
  -H "Authorization: Bearer YOUR_TOKEN" /
  -H "Content-Type: application/json" /
  -d '{"name": "My First Experiment"}'

# 4. Open interactive docs
open http://localhost:8000/docs
```

### Run the Example Notebook

```bash
# 1. Install Jupyter
pip install jupyter

# 2. Open notebook
jupyter notebook notebooks/example_pipeline.ipynb

# 3. Run all cells (Cell → Run All)
```

### Local Development

**Backend:**
```bash
cd services/api

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start dev server (hot reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd services/dashboard

# Install dependencies
npm install

# Start dev server
npm start

# Opens http://localhost:3000
```

### Project Structure Tour

```
BioTechDemo/
├── services/
│   ├── api/              ← Backend (FastAPI)
│   │   ├── app/
│   │   │   ├── main.py        Entry point
│   │   │   ├── routers/       API endpoints
│   │   │   ├── db.py          Database models
│   │   │   └── ml/            ML inference
│   │   └── tests/        Unit tests
│   └── dashboard/        ← Frontend (React)
│       └── src/
│           ├── components/    React components
│           └── pages/         Page layouts
├── lib/
│   └── openbioops/       ← Shared Python library
│       ├── processing.py      Data processing
│       └── models.py          Data structures
├── ml/
│   ├── train.py          ← ML training script
│   ├── model.py          Neural network
│   └── mlflow_config.py  Experiment tracking
├── notebooks/
│   └── example_pipeline.ipynb  ← Jupyter tutorial
├── pipelines/
│   ├── main.nf           Nextflow pipeline
│   └── workflow.wdl      WDL pipeline
├── infra/
│   ├── terraform/        Infrastructure as Code
│   └── k8s/              Kubernetes configs
├── tests/                ← Integration tests
├── docker-compose.yml    ← Multi-container setup
└── README.md             Main documentation
```

---

## Glossary of Terms

### API Terms

- **API (Application Programming Interface)**: A way for programs to talk to each other
- **Endpoint**: A specific URL that provides a function (e.g., `/v1/runs`)
- **REST (Representational State Transfer)**: A style of designing APIs
- **HTTP**: Protocol for web communication (GET, POST, PUT, DELETE)
- **JSON**: Text format for data (like `{"key": "value"}`)
- **CRUD**: Create, Read, Update, Delete (basic operations)

### Database Terms

- **Schema**: Structure of database tables
- **Primary Key**: Unique identifier for a row
- **Foreign Key**: Reference to another table
- **Index**: Makes queries faster (like a book index)
- **Migration**: Script that updates database structure
- **Transaction**: Group of operations that succeed or fail together
- **ORM (Object-Relational Mapping)**: Use Python instead of SQL

### ML Terms

- **Model**: Trained algorithm that makes predictions
- **Training**: Process of teaching a model from data
- **Inference**: Using a trained model to make predictions
- **Embedding**: Representation of data as a vector of numbers
- **Loss function**: Measures how wrong the model is
- **Epoch**: One pass through entire training dataset
- **Batch**: Subset of data processed together

### DevOps Terms

- **Container**: Packaged application with all dependencies
- **Image**: Template for containers (like a class in OOP)
- **Orchestration**: Managing many containers automatically
- **CI/CD**: Automated testing and deployment
- **IaC (Infrastructure as Code)**: Define servers/networks in code files
- **Blue-Green Deployment**: Run two versions, switch traffic instantly
- **Auto-scaling**: Automatically add/remove servers based on load

### Python Terms

- **Decorator**: Function that modifies another function (`@app.route`)
- **Generator**: Function that yields values one at a time
- **Comprehension**: Concise way to create lists `[x for x in range(10)]`
- **Context Manager**: Automatic resource cleanup (`with` statement)
- **Type Hints**: Optional type annotations (`def f(x: int) -> str`)
- **Virtual Environment**: Isolated Python installation for a project

### React Terms

- **Component**: Reusable piece of UI
- **Props**: Data passed to a component
- **State**: Data that can change over time
- **Hook**: Function that lets you use React features (`useState`, `useEffect`)
- **JSX**: HTML-like syntax in JavaScript
- **Virtual DOM**: React's internal representation of UI

### Cloud Terms

- **VPC (Virtual Private Cloud)**: Isolated network in cloud
- **Load Balancer**: Distributes traffic across servers
- **Auto Scaling**: Automatically add/remove servers
- **Region**: Geographic location of data centers
- **Availability Zone**: Isolated data center within region
- **S3**: Amazon's file storage service

---

## Conclusion

Congratulations! You now have a comprehensive understanding of OpenBioOps and modern software architecture.

### What You Learned

**Conceptual:**
- How modern web applications work (client-server, three-tier)
- Why we separate concerns (frontend, backend, database)
- What each technology does and why we use it
- How data flows through the system

**Technical:**
- APIs and REST principles
- Databases and SQL
- Machine learning basics
- Docker containers and Kubernetes
- CI/CD pipelines
- Infrastructure as Code

**Practical:**
- How to read the codebase
- Common patterns you'll see everywhere
- How to get started with development
- Where to look for specific functionality

### Next Steps

**Beginner Level:**
1. Run the example notebook
2. Explore the API docs (http://localhost:8000/docs)
3. Make a small change to the frontend
4. Add a print statement in the backend

**Intermediate Level:**
1. Add a new API endpoint
2. Modify the ML model architecture
3. Create a new React component
4. Write unit tests for your changes

**Advanced Level:**
1. Implement a new feature end-to-end
2. Optimize database queries
3. Add Kubernetes auto-scaling
4. Build a new ML pipeline

### Resources for Learning More

**Python & FastAPI:**
- Official Python tutorial: docs.python.org/tutorial
- FastAPI documentation: fastapi.tiangolo.com
- Real Python tutorials: realpython.com

**React:**
- Official React tutorial: react.dev/learn
- Modern JavaScript: javascript.info

**Machine Learning:**
- Fast.ai course: course.fast.ai
- PyTorch tutorials: pytorch.org/tutorials

**DevOps:**
- Docker documentation: docs.docker.com
- Kubernetes basics: kubernetes.io/docs/tutorials

**Bioinformatics:**
- scanpy tutorials: scanpy.tutorials.readthedocs.io
- Single-cell best practices: www.sc-best-practices.org

### Questions to Explore

1. How would you add a new cell type classifier?
2. What happens if the database crashes?
3. How would you make the system handle 10x more traffic?
4. Can you add real-time notifications when processing completes?
5. How would you implement user permissions (admin vs. read-only)?

### Remember

- Don't be intimidated by the complexity - no one knows everything
- Start small, make incremental changes
- Read error messages carefully - they usually tell you what's wrong
- Google and Stack Overflow are your friends
- The best way to learn is by doing

**Good luck on your journey! Welcome to enterprise software development! **
