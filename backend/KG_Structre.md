# Tech Knowledge Graph — README

## Purpose

This graph models the **transferability of technical knowledge** across the technology market. It is designed to power **context-aware matching** between candidate profiles and job descriptions — going beyond exact keyword matching by understanding that knowing React transfers to Vue, that Kubernetes experience subsumes Helm, and that Python is the lingua franca of the entire ML/Data/LLM stack.

---

## File

```
tech_knowledge_graph.cypher   — Neo4j Cypher import script
```

Import with:

```bash
# From Neo4j Browser
:source tech_knowledge_graph.cypher

# From the command line
cypher-shell -u neo4j -p <password> < tech_knowledge_graph.cypher
```

---

## Graph Statistics

| Element         | Count |
|-----------------|-------|
| Technology nodes | 248  |
| Relationships   | 284   |
| Edge types      | 9     |
| Domains covered | 12    |

---

## Node Structure

Every node carries a single label `Technology` with the following properties:

| Property   | Type   | Description |
|------------|--------|-------------|
| `name`     | String | Canonical display name (e.g. `"React"`, `"Kubernetes"`) |
| `category` | String | **Coarse role label** used for matching and filtering (see below) |
| `domain`   | String | Fine-grained sub-domain (e.g. `"NLP"`, `"CICD"`, `"VectorDB"`) |
| `type`     | String | Structural kind: `Language`, `Framework`, `Library`, `Platform`, `Protocol`, `Standard`, … |
| `language` | String | Implementation or primary language (e.g. `"Python"`, `"YAML"`, `"Agnostic"`) |
| `tags`     | String | Comma-separated keywords for full-text search (e.g. `"ssr,ssg,fullstack,react"`) |

### Category Values

The `category` property is the primary handle for grouping and scoring:

| Category          | What it covers |
|-------------------|----------------|
| `Frontend`        | UI frameworks, bundlers, CSS tools, state managers, testing |
| `FullStack`       | SSR/meta-frameworks that span client and server (Next.js, Remix, Nuxt) |
| `Backend`         | Server runtimes, backend languages and HTTP frameworks |
| `Mobile`          | Cross-platform and native mobile development |
| `DevOps`          | Containers, orchestration, proxies, service mesh, secrets |
| `IaC`             | Infrastructure-as-Code and configuration management |
| `CICD`            | CI/CD pipelines and GitOps tools |
| `Observability`   | Metrics, logging, tracing and APM platforms |
| `Cloud`           | Cloud platforms, managed Kubernetes, serverless, hosting |
| `Database`        | Relational, document, graph, wide-column, time-series |
| `Cache`           | In-memory key-value caches |
| `Search`          | Full-text search and analytics engines |
| `VectorDB`        | Vector databases for AI/embedding workloads |
| `DataWarehouse`   | OLAP engines and cloud data warehouses |
| `MessageBroker`   | Message queues, event streams and event buses |
| `DataEngineering` | Data processing, orchestration, lakehouse formats, analysis |
| `MLOps`           | ML experiment tracking, model serving, feature stores, drift monitoring |
| `ML`              | Machine learning and deep learning frameworks and runtimes |
| `LLM`             | Large language model providers, orchestration frameworks and agents |
| `Security`        | Penetration testing, SIEM, EDR, IAM, policy-as-code |
| `API`             | API protocols, gateways, documentation and testing tools |

---

## Relationship Types

All edges are **directional** and encode a specific semantic meaning. There is no `COMPETES_WITH` edge — the graph is focused entirely on knowledge flow and technical necessity.

### `TRANSFERABLE_TO`

> Knowledge of A significantly helps learning or using B.

This is the **core matching edge**. It captures the most important insight for profile-job matching: that a developer who knows Express will onboard quickly to Fastify, that a Cassandra DBA can operate ScyllaDB, that PyTorch skills transfer to TensorFlow.

Properties: `reason` (string), `weight` (float 0–1)

The `weight` represents how much of A's knowledge carries over to B:
- **0.90–1.00** — near-complete transfer (Vitest ↔ Jest, OpenSearch → Elasticsearch)
- **0.80–0.89** — strong transfer, minor paradigm shift
- **0.70–0.79** — moderate transfer, new concepts required
- **0.60–0.69** — partial transfer, significant new learning needed

---

### `EQUIVALENT_IN`

> A and B solve the **exact same problem** in different ecosystems.

Used when two technologies occupy identical roles but in different language or cloud ecosystems. The canonical examples are:

- `Next.js` ↔ `Nuxt.js` (React vs Vue SSR meta-framework)
- `NestJS` ↔ `Spring Boot` (DI enterprise backend, Node vs Java)
- `AWS EKS` ↔ `GCP GKE` ↔ `Azure AKS` (managed Kubernetes)
- `Feast` ↔ `Tecton` (feature store)
- `AWS Lambda` ↔ `GCP Cloud Functions` ↔ `Azure Functions` (FaaS)

Weight is typically **0.85–0.98** because the conceptual overlap is near-total.

---

### `EXTENDS`

> A is built **on top of** B and adds capability to it.

The user of A implicitly must understand B. All of A's users are effective users of B.

Examples:
- `Keras` → `TensorFlow` (Keras is TF's high-level API)
- `TypeScript` → `JavaScript` (TS is a typed JS superset)
- `TimescaleDB` → `PostgreSQL` (Postgres extension)
- `Expo` → `React Native` (managed RN platform)
- `LangGraph` → `LangChain` (stateful agent layer on top of LangChain)

---

### `REQUIRES`

> Using A **in practice requires** knowing B. Hard dependency.

This is stronger than `EXTENDS`. It captures runtime dependencies, language requirements and platform prerequisites.

Examples:
- `Next.js` → `React` (you must know React to use Next.js)
- `Helm` → `Kubernetes` (Helm charts only make sense on K8s)
- `Spring Boot` → `Java`
- `Ktor` → `Kotlin`
- `TorchServe` → `PyTorch`

This edge is used to **expand** a candidate's effective skill set: if they list `Next.js`, they implicitly know `React`.

---

### `OFTEN_USED_WITH`

> A and B are **strongly co-located** in real-world stacks.

Not a hard dependency, but a strong co-occurrence signal. Useful for boosting matching scores when both appear together.

Examples:
- `Prometheus` ↔ `Grafana`
- `Angular` ↔ `RxJS`
- `Vite` ↔ `Vitest`
- `Kafka` ↔ `Spark`
- `dbt` ↔ `Snowflake`

---

### `PART_OF`

> A is a **sub-component or layer** of a larger platform B.

Examples:
- `HF Transformers` → `Hugging Face` (the core library of the HF ecosystem)
- `HF Diffusers` → `Hugging Face`

Knowing A implies familiarity with the B ecosystem.

---

### `BRIDGES`

> A **connects two distinct domains** or serves as the glue between ecosystems.

This captures technologies that are inherently cross-domain. Finding a `BRIDGES` node in a traversal path is a strong signal that a candidate has cross-domain capability.

Examples:
- `Python` → `TensorFlow` / `scikit-learn` / `LangChain` (bridges Backend ↔ ML ↔ LLM)
- `Node.js` → `JavaScript` (bridges Frontend ↔ Backend)
- `ONNX` → `PyTorch` / `TensorFlow` / `Triton` (bridges training ↔ inference)
- `OpenTelemetry` → `Prometheus` / `Datadog` (bridges code ↔ observability)
- `Kubernetes` → `Kubeflow` (bridges DevOps ↔ MLOps)

---

### `EVOLVED_INTO`

> A is the **modern successor** that superseded B.

Direction: new → old (A evolved into the space previously occupied by B).

Examples:
- `Vite` → `Webpack` (Vite supersedes Webpack as the default dev server)
- `Kotlin` → `Java` (Kotlin is the modern JVM language)
- `Polars` → `Pandas` (Polars is the high-performance Pandas replacement)
- `OpenSearch` → `Elasticsearch` (OpenSearch forked and replaced ES in many stacks)

When scoring, knowledge of the successor implies familiarity with the predecessor's concepts.

---

### `IMPLEMENTS`

> A is a **concrete implementation** of protocol or standard B.

Examples:
- `Keycloak` → `OAuth 2.0` (Keycloak is a full OAuth2/OIDC server)

Knowing the implementation implies knowing the standard.

---

## How to Use for Matching

### 1. Expand a candidate's effective skill set

Traverse `TRANSFERABLE_TO`, `EQUIVALENT_IN`, `EXTENDS`, `REQUIRES` and `PART_OF` edges up to 2 hops to generate a broader set of "skills the candidate is likely to know or learn quickly":

```cypher
MATCH (t:Technology)
WHERE t.name IN $profile_skills
OPTIONAL MATCH (t)-[:TRANSFERABLE_TO|EQUIVALENT_IN|EXTENDS|REQUIRES|PART_OF*1..2]-(related)
RETURN collect(DISTINCT t.name) + collect(DISTINCT related.name) AS expanded_skills
```

### 2. Compute a weighted match score

```cypher
MATCH (pt:Technology) WHERE pt.name IN $profile_skills
OPTIONAL MATCH (pt)-[r:TRANSFERABLE_TO|EQUIVALENT_IN]->(related:Technology)
WITH collect(DISTINCT pt.name) AS direct,
     collect({name: related.name, weight: r.weight}) AS transferred

// Count exact matches (weight 1.0) plus weighted partial matches
MATCH (jt:Technology) WHERE jt.name IN $job_skills
RETURN
  size([s IN direct WHERE s IN $job_skills]) AS exact_matches,
  size($job_skills) AS total_required
```

### 3. Category-level matching

For jobs that specify a domain (e.g. "Backend Engineer"), filter by `category`:

```cypher
MATCH (t:Technology)
WHERE t.name IN $job_skills AND t.category IN ["Backend", "Database", "API"]
RETURN t.name, t.category
```

### 4. Find the bridge nodes connecting two domains

Useful for discovering whether a candidate has cross-domain potential (e.g. Backend → ML):

```cypher
MATCH (a:Technology {category:"Backend"})-[:BRIDGES]->(b:Technology {category:"ML"})
RETURN a.name, b.name
```

### 5. Inspect transferability chains

See why a candidate with "Express" experience is relevant to a "NestJS" job:

```cypher
MATCH path = (a:Technology {name:"Express.js"})-[:TRANSFERABLE_TO*1..3]->(b:Technology {name:"NestJS"})
RETURN path
```

---

## Domain Coverage

| Domain            | Key technologies covered |
|-------------------|--------------------------|
| **Frontend**      | React, Vue, Angular, Svelte, Next.js, Nuxt, Remix, Vite, Webpack, Tailwind, Redux, Zustand, Pinia, Jest, Playwright, TypeScript |
| **Backend**       | Node.js, Express, FastAPI, Django, Spring Boot, Quarkus, Gin, Fiber, Axum, .NET, Laravel, Rails, Phoenix, NestJS |
| **Database**      | PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch, Cassandra, ScyllaDB, DynamoDB, Neo4j, InfluxDB, ClickHouse, Snowflake, BigQuery |
| **Vector DB**     | Pinecone, Weaviate, Qdrant, ChromaDB, Milvus |
| **DevOps**        | Docker, Kubernetes, Helm, Terraform, Ansible, GitHub Actions, Argo CD, Nginx, Traefik, Istio, Vault |
| **Observability** | Prometheus, Grafana, Loki, ELK, Datadog, OpenTelemetry, Jaeger |
| **Cloud**         | AWS, GCP, Azure, EKS, GKE, AKS, Lambda, Cloud Functions, Vercel, Netlify |
| **Messaging**     | Kafka, RabbitMQ, NATS, Pulsar, SQS, Kinesis, EventBridge |
| **Data Eng.**     | Spark, Flink, Airflow, Prefect, Dagster, dbt, Delta Lake, Pandas, Polars, NumPy |
| **MLOps**         | MLflow, Kubeflow, BentoML, Seldon, KServe, Triton, DVC, W&B, Feast, Tecton, Ray, SageMaker, Vertex AI |
| **ML**            | TensorFlow, PyTorch, JAX, Keras, scikit-learn, XGBoost, LightGBM, HuggingFace, spaCy, ONNX, vLLM |
| **LLM**           | OpenAI, Anthropic, Gemini, LangChain, LlamaIndex, LangGraph, AutoGen, CrewAI, DSPy, LiteLLM, Guardrails |
| **Security**      | Burp Suite, Metasploit, Nmap, Splunk, Wazuh, Falco, OPA, Trivy, Keycloak, OAuth 2.0, JWT |
| **Mobile**        | React Native, Flutter, Swift, Kotlin Android, Ionic, Expo |
| **API**           | REST, GraphQL, gRPC, tRPC, Swagger/OpenAPI, Kong, Apigee, Postman |

---

## Design Decisions

**No `COMPETES_WITH` edges.** Competition is a market concept, not a knowledge concept. Two tools that compete (PostgreSQL and MySQL) still share transferable SQL and RDBMS skills. Modelling competition adds noise to traversal-based scoring without improving match quality.

**Directed edges.** All edges have a specific direction encoding the knowledge flow. `Flask → FastAPI` via `TRANSFERABLE_TO` means Flask experience helps learn FastAPI — not necessarily the reverse at the same weight.

**`weight` property.** Used to discount partial transfers in weighted matching. A candidate with React experience gets 0.85 credit toward a Vue job, not 1.0.

**`category` vs `domain`.** Category is the coarse label for matching and filtering (e.g. `ML`). Domain is finer-grained for display and exploration (e.g. `GradientBoosting`, `NLP`, `Inference`). Matching queries should use `category`; visualisation can use `domain`.
