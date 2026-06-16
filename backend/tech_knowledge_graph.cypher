// =============================================================================
// TECH KNOWLEDGE GRAPH — Neo4j Cypher
// Purpose : Model technology transferability and necessity for profile-job matching
//
// Node label  : Technology
// Node props  :
//   name       — canonical display name
//   category   — coarse role label used for matching (see list below)
//   domain     — fine-grained sub-domain
//   type       — structural kind (Language, Framework, Library, …)
//   language   — implementation / primary language
//   tags       — comma-separated keywords
//
// Category values used in this file:
//   Frontend | Backend | FullStack | Mobile
//   DevOps | Cloud | IaC | CICD | Observability | Security
//   Database | Cache | Search | VectorDB | DataWarehouse | MessageBroker
//   DataEngineering | MLOps | ML | LLM | API
//
// Edge types (all directional — read as "A → B"):
//   TRANSFERABLE_TO   knowledge of A transfers significantly to learning B
//   EQUIVALENT_IN     A and B solve the exact same problem in different ecosystems
//   EXTENDS           A is built on top of B / adds capability to B
//   REQUIRES          using A in practice requires knowing B (hard dependency)
//   OFTEN_USED_WITH   A and B are strongly co-located in real stacks
//   PART_OF           A is a sub-component/layer of B
//   BRIDGES           A spans or connects two distinct domains
//   IMPLEMENTS        A is a concrete implementation of protocol/standard B
//   EVOLVED_INTO      A is the modern successor that replaced B
//
// Edge props :
//   reason  — human-readable justification
//   weight  — transferability score 0..1 (used in matching formulas)
// =============================================================================

// ─────────────────────────────────────────────────────────────────────────────
// 1. NODE DEFINITIONS
// ─────────────────────────────────────────────────────────────────────────────

// ── FRONTEND UI FRAMEWORKS ────────────────────────────────────────────────────
MERGE (react:Technology       {name:"React",          category:"Frontend",      domain:"Frontend",       type:"Library",       language:"JavaScript", tags:"component,virtual-dom,spa"})
MERGE (angular:Technology     {name:"Angular",        category:"Frontend",      domain:"Frontend",       type:"Framework",     language:"TypeScript",  tags:"component,di,spa,rxjs"})
MERGE (vue:Technology         {name:"Vue.js",         category:"Frontend",      domain:"Frontend",       type:"Framework",     language:"JavaScript",  tags:"component,reactive,spa"})
MERGE (svelte:Technology      {name:"Svelte",         category:"Frontend",      domain:"Frontend",       type:"Framework",     language:"JavaScript",  tags:"compile-time,reactive,spa"})
MERGE (solidjs:Technology     {name:"SolidJS",        category:"Frontend",      domain:"Frontend",       type:"Framework",     language:"JavaScript",  tags:"fine-grained-reactivity,spa"})

// ── SSR / META-FRAMEWORKS ─────────────────────────────────────────────────────
MERGE (nextjs:Technology      {name:"Next.js",        category:"FullStack",     domain:"Frontend",       type:"Meta-Framework", language:"JavaScript", tags:"ssr,ssg,fullstack,react"})
MERGE (nuxtjs:Technology      {name:"Nuxt.js",        category:"FullStack",     domain:"Frontend",       type:"Meta-Framework", language:"JavaScript", tags:"ssr,ssg,fullstack,vue"})
MERGE (remix:Technology       {name:"Remix",          category:"FullStack",     domain:"Frontend",       type:"Meta-Framework", language:"JavaScript", tags:"ssr,fullstack,react"})
MERGE (astro:Technology       {name:"Astro",          category:"Frontend",      domain:"Frontend",       type:"Framework",     language:"JavaScript",  tags:"static-site,island-arch"})
MERGE (gatsby:Technology      {name:"Gatsby",         category:"Frontend",      domain:"Frontend",       type:"Framework",     language:"JavaScript",  tags:"ssg,react,graphql"})

// ── BUILD TOOLS ───────────────────────────────────────────────────────────────
MERGE (webpack:Technology     {name:"Webpack",        category:"Frontend",      domain:"Frontend",       type:"Bundler",       language:"JavaScript",  tags:"build,module-bundler"})
MERGE (vite:Technology        {name:"Vite",           category:"Frontend",      domain:"Frontend",       type:"Bundler",       language:"JavaScript",  tags:"build,esm,fast"})
MERGE (rollup:Technology      {name:"Rollup",         category:"Frontend",      domain:"Frontend",       type:"Bundler",       language:"JavaScript",  tags:"build,library-bundler"})
MERGE (esbuild:Technology     {name:"esbuild",        category:"Frontend",      domain:"Frontend",       type:"Bundler",       language:"Go",          tags:"build,fast"})
MERGE (turbopack:Technology   {name:"Turbopack",      category:"Frontend",      domain:"Frontend",       type:"Bundler",       language:"Rust",        tags:"build,fast,webpack-successor"})

// ── CSS / UI LIBRARIES ────────────────────────────────────────────────────────
MERGE (tailwind:Technology    {name:"Tailwind CSS",   category:"Frontend",      domain:"Frontend",       type:"CSS Framework", language:"CSS",         tags:"utility-first,css"})
MERGE (bootstrap:Technology   {name:"Bootstrap",      category:"Frontend",      domain:"Frontend",       type:"CSS Framework", language:"CSS",         tags:"component-library,css"})
MERGE (materialui:Technology  {name:"Material UI",    category:"Frontend",      domain:"Frontend",       type:"UI Library",    language:"JavaScript",  tags:"component-library,react,google-design"})
MERGE (shadcn:Technology      {name:"shadcn/ui",      category:"Frontend",      domain:"Frontend",       type:"UI Library",    language:"TypeScript",  tags:"component-library,react,tailwind"})
MERGE (storybook:Technology   {name:"Storybook",      category:"Frontend",      domain:"Frontend",       type:"DevTool",       language:"JavaScript",  tags:"component-explorer,design-system"})

// ── STATE / DATA ──────────────────────────────────────────────────────────────
MERGE (graphql:Technology     {name:"GraphQL",        category:"API",           domain:"API",            type:"Query Language", language:"Agnostic",   tags:"api,query,schema"})
MERGE (apollo:Technology      {name:"Apollo Client",  category:"Frontend",      domain:"Frontend",       type:"State/Data",    language:"JavaScript",  tags:"graphql-client,state"})
MERGE (reactquery:Technology  {name:"React Query",    category:"Frontend",      domain:"Frontend",       type:"State/Data",    language:"JavaScript",  tags:"server-state,caching"})
MERGE (redux:Technology       {name:"Redux",          category:"Frontend",      domain:"Frontend",       type:"State Mgmt",    language:"JavaScript",  tags:"global-state,flux"})
MERGE (zustand:Technology     {name:"Zustand",        category:"Frontend",      domain:"Frontend",       type:"State Mgmt",    language:"JavaScript",  tags:"global-state,simple"})
MERGE (mobx:Technology        {name:"MobX",           category:"Frontend",      domain:"Frontend",       type:"State Mgmt",    language:"JavaScript",  tags:"reactive-state"})
MERGE (pinia:Technology       {name:"Pinia",          category:"Frontend",      domain:"Frontend",       type:"State Mgmt",    language:"JavaScript",  tags:"global-state,vue"})
MERGE (rxjs:Technology        {name:"RxJS",           category:"Frontend",      domain:"Frontend",       type:"Library",       language:"JavaScript",  tags:"reactive,observable,async"})

// ── FRONTEND TESTING ──────────────────────────────────────────────────────────
MERGE (jest:Technology        {name:"Jest",           category:"Frontend",      domain:"Frontend",       type:"Testing",       language:"JavaScript",  tags:"unit-test,mock"})
MERGE (vitest:Technology      {name:"Vitest",         category:"Frontend",      domain:"Frontend",       type:"Testing",       language:"JavaScript",  tags:"unit-test,vite"})
MERGE (cypress:Technology     {name:"Cypress",        category:"Frontend",      domain:"Frontend",       type:"Testing",       language:"JavaScript",  tags:"e2e-test"})
MERGE (playwright:Technology  {name:"Playwright",     category:"Frontend",      domain:"Frontend",       type:"Testing",       language:"JavaScript",  tags:"e2e-test,cross-browser"})

// ── LANGUAGES ─────────────────────────────────────────────────────────────────
MERGE (typescript:Technology  {name:"TypeScript",     category:"Frontend",      domain:"Language",       type:"Language",      language:"TypeScript",  tags:"typed,superset-js"})
MERGE (javascript:Technology  {name:"JavaScript",     category:"Frontend",      domain:"Language",       type:"Language",      language:"JavaScript",  tags:"scripting,web"})
MERGE (wasm:Technology        {name:"WebAssembly",    category:"Frontend",      domain:"Frontend",       type:"Runtime",       language:"Binary",      tags:"performance,native-speed"})
MERGE (pwa:Technology         {name:"PWA",            category:"Frontend",      domain:"Frontend",       type:"Pattern",       language:"JavaScript",  tags:"offline,service-worker"})

// ── BACKEND RUNTIMES & FRAMEWORKS ────────────────────────────────────────────
MERGE (nodejs:Technology      {name:"Node.js",        category:"Backend",       domain:"Backend",        type:"Runtime",       language:"JavaScript",  tags:"event-loop,non-blocking,server"})
MERGE (express:Technology     {name:"Express.js",     category:"Backend",       domain:"Backend",        type:"Framework",     language:"JavaScript",  tags:"http,minimal,rest"})
MERGE (fastify:Technology     {name:"Fastify",        category:"Backend",       domain:"Backend",        type:"Framework",     language:"JavaScript",  tags:"http,fast,rest"})
MERGE (nestjs:Technology      {name:"NestJS",         category:"Backend",       domain:"Backend",        type:"Framework",     language:"TypeScript",  tags:"oop,di,rest,graphql"})
MERGE (hono:Technology        {name:"Hono",           category:"Backend",       domain:"Backend",        type:"Framework",     language:"TypeScript",  tags:"edge,lightweight,rest"})
MERGE (python:Technology      {name:"Python",         category:"Backend",       domain:"Language",       type:"Language",      language:"Python",      tags:"scripting,data,general"})
MERGE (django:Technology      {name:"Django",         category:"Backend",       domain:"Backend",        type:"Framework",     language:"Python",      tags:"full-stack,orm,batteries-included"})
MERGE (fastapi:Technology     {name:"FastAPI",        category:"Backend",       domain:"Backend",        type:"Framework",     language:"Python",      tags:"async,rest,openapi"})
MERGE (flask:Technology       {name:"Flask",          category:"Backend",       domain:"Backend",        type:"Framework",     language:"Python",      tags:"minimal,rest"})
MERGE (java:Technology        {name:"Java",           category:"Backend",       domain:"Language",       type:"Language",      language:"Java",        tags:"jvm,oop,enterprise"})
MERGE (springboot:Technology  {name:"Spring Boot",    category:"Backend",       domain:"Backend",        type:"Framework",     language:"Java",        tags:"di,rest,enterprise,jvm"})
MERGE (quarkus:Technology     {name:"Quarkus",        category:"Backend",       domain:"Backend",        type:"Framework",     language:"Java",        tags:"native,jvm,cloud-native"})
MERGE (micronaut:Technology   {name:"Micronaut",      category:"Backend",       domain:"Backend",        type:"Framework",     language:"Java",        tags:"aot,jvm,cloud-native"})
MERGE (kotlin:Technology      {name:"Kotlin",         category:"Backend",       domain:"Language",       type:"Language",      language:"Kotlin",      tags:"jvm,oop,functional"})
MERGE (ktor:Technology        {name:"Ktor",           category:"Backend",       domain:"Backend",        type:"Framework",     language:"Kotlin",      tags:"async,jvm,rest"})
MERGE (scala:Technology       {name:"Scala",          category:"Backend",       domain:"Language",       type:"Language",      language:"Scala",       tags:"jvm,functional,oop"})
MERGE (akka:Technology        {name:"Akka",           category:"Backend",       domain:"Backend",        type:"Framework",     language:"Scala",       tags:"actor-model,reactive,jvm"})
MERGE (golang:Technology      {name:"Go",             category:"Backend",       domain:"Language",       type:"Language",      language:"Go",          tags:"compiled,concurrent,cloud-native"})
MERGE (gin:Technology         {name:"Gin",            category:"Backend",       domain:"Backend",        type:"Framework",     language:"Go",          tags:"http,rest,fast"})
MERGE (fiber:Technology       {name:"Fiber",          category:"Backend",       domain:"Backend",        type:"Framework",     language:"Go",          tags:"http,rest,express-inspired"})
MERGE (rust:Technology        {name:"Rust",           category:"Backend",       domain:"Language",       type:"Language",      language:"Rust",        tags:"systems,memory-safe,performance"})
MERGE (actix:Technology       {name:"Actix-web",      category:"Backend",       domain:"Backend",        type:"Framework",     language:"Rust",        tags:"http,rest,actor"})
MERGE (axum:Technology        {name:"Axum",           category:"Backend",       domain:"Backend",        type:"Framework",     language:"Rust",        tags:"http,rest,tokio"})
MERGE (csharp:Technology      {name:"C#",             category:"Backend",       domain:"Language",       type:"Language",      language:"C#",          tags:"dotnet,oop,microsoft"})
MERGE (dotnet:Technology      {name:".NET / ASP.NET", category:"Backend",       domain:"Backend",        type:"Framework",     language:"C#",          tags:"enterprise,rest,microsoft"})
MERGE (php:Technology         {name:"PHP",            category:"Backend",       domain:"Language",       type:"Language",      language:"PHP",         tags:"web,scripting"})
MERGE (laravel:Technology     {name:"Laravel",        category:"Backend",       domain:"Backend",        type:"Framework",     language:"PHP",         tags:"full-stack,orm,rest"})
MERGE (symfony:Technology     {name:"Symfony",        category:"Backend",       domain:"Backend",        type:"Framework",     language:"PHP",         tags:"enterprise,components"})
MERGE (ruby:Technology        {name:"Ruby",           category:"Backend",       domain:"Language",       type:"Language",      language:"Ruby",        tags:"scripting,elegant"})
MERGE (rails:Technology       {name:"Ruby on Rails",  category:"Backend",       domain:"Backend",        type:"Framework",     language:"Ruby",        tags:"full-stack,convention-over-config,orm"})
MERGE (elixir:Technology      {name:"Elixir",         category:"Backend",       domain:"Language",       type:"Language",      language:"Elixir",      tags:"functional,actor,beam"})
MERGE (phoenix:Technology     {name:"Phoenix",        category:"Backend",       domain:"Backend",        type:"Framework",     language:"Elixir",      tags:"full-stack,realtime,beam"})

// ── API PATTERNS & PROTOCOLS ─────────────────────────────────────────────────
MERGE (graphqlserver:Technology{name:"GraphQL Server",category:"API",           domain:"API",            type:"Pattern",       language:"Agnostic",    tags:"api,schema,resolver"})
MERGE (rest:Technology        {name:"REST API",       category:"API",           domain:"API",            type:"Pattern",       language:"Agnostic",    tags:"api,http,stateless"})
MERGE (grpc:Technology        {name:"gRPC",           category:"API",           domain:"API",            type:"Protocol",      language:"Agnostic",    tags:"rpc,protobuf,microservices"})
MERGE (websocket:Technology   {name:"WebSocket",      category:"Backend",       domain:"API",            type:"Protocol",      language:"Agnostic",    tags:"realtime,bidirectional"})
MERGE (trpc:Technology        {name:"tRPC",           category:"FullStack",     domain:"API",            type:"Framework",     language:"TypeScript",  tags:"type-safe-api,fullstack"})
MERGE (swagger:Technology     {name:"Swagger/OpenAPI",category:"API",           domain:"API",            type:"Standard",      language:"YAML",        tags:"api-spec,documentation,codegen"})
MERGE (postman:Technology     {name:"Postman",        category:"API",           domain:"API",            type:"Tool",          language:"Agnostic",    tags:"api-testing,mocking,docs"})
MERGE (apigee:Technology      {name:"Apigee",         category:"API",           domain:"API",            type:"Gateway",       language:"Agnostic",    tags:"api-management,gcp,gateway"})
MERGE (kong:Technology        {name:"Kong",           category:"API",           domain:"API",            type:"Gateway",       language:"Lua",         tags:"api-gateway,rate-limit,plugin"})
MERGE (aws_apigw:Technology   {name:"AWS API GW",     category:"API",           domain:"API",            type:"Gateway",       language:"Agnostic",    tags:"api-gateway,aws,serverless"})

// ── DATABASES ────────────────────────────────────────────────────────────────
MERGE (postgres:Technology    {name:"PostgreSQL",     category:"Database",      domain:"RDBMS",          type:"RDBMS",         language:"SQL",         tags:"relational,acid,open-source"})
MERGE (mysql:Technology       {name:"MySQL",          category:"Database",      domain:"RDBMS",          type:"RDBMS",         language:"SQL",         tags:"relational,acid,web"})
MERGE (sqlite:Technology      {name:"SQLite",         category:"Database",      domain:"RDBMS",          type:"RDBMS",         language:"SQL",         tags:"embedded,lightweight"})
MERGE (mssql:Technology       {name:"SQL Server",     category:"Database",      domain:"RDBMS",          type:"RDBMS",         language:"SQL",         tags:"relational,enterprise,microsoft"})
MERGE (oracle:Technology      {name:"Oracle DB",      category:"Database",      domain:"RDBMS",          type:"RDBMS",         language:"SQL",         tags:"relational,enterprise"})
MERGE (mongodb:Technology     {name:"MongoDB",        category:"Database",      domain:"DocumentDB",     type:"Document DB",   language:"NoSQL",       tags:"document,flexible-schema"})
MERGE (couchdb:Technology     {name:"CouchDB",        category:"Database",      domain:"DocumentDB",     type:"Document DB",   language:"NoSQL",       tags:"document,replication"})
MERGE (redis:Technology       {name:"Redis",          category:"Cache",         domain:"Cache",          type:"Cache/KV",      language:"NoSQL",       tags:"in-memory,cache,pubsub"})
MERGE (memcached:Technology   {name:"Memcached",      category:"Cache",         domain:"Cache",          type:"Cache",         language:"NoSQL",       tags:"in-memory,cache"})
MERGE (elasticsearch:Technology{name:"Elasticsearch", category:"Search",        domain:"Search",         type:"Search Engine", language:"NoSQL",       tags:"full-text-search,analytics"})
MERGE (opensearch:Technology  {name:"OpenSearch",     category:"Search",        domain:"Search",         type:"Search Engine", language:"NoSQL",       tags:"full-text-search,analytics"})
MERGE (cassandra:Technology   {name:"Cassandra",      category:"Database",      domain:"WideColumn",     type:"Wide-column",   language:"NoSQL",       tags:"distributed,high-write,time-series"})
MERGE (scylladb:Technology    {name:"ScyllaDB",       category:"Database",      domain:"WideColumn",     type:"Wide-column",   language:"NoSQL",       tags:"cassandra-compatible,high-perf"})
MERGE (dynamodb:Technology    {name:"DynamoDB",       category:"Database",      domain:"KV",             type:"KV/Document",   language:"NoSQL",       tags:"managed,serverless,aws"})
MERGE (firestore:Technology   {name:"Firestore",      category:"Database",      domain:"DocumentDB",     type:"Document DB",   language:"NoSQL",       tags:"managed,realtime,gcp"})
MERGE (neo4j:Technology       {name:"Neo4j",          category:"Database",      domain:"GraphDB",        type:"Graph DB",      language:"NoSQL",       tags:"graph,cypher,relationships"})
MERGE (tigergraph:Technology  {name:"TigerGraph",     category:"Database",      domain:"GraphDB",        type:"Graph DB",      language:"NoSQL",       tags:"graph,analytics"})
MERGE (influxdb:Technology    {name:"InfluxDB",       category:"Database",      domain:"TimeSeries",     type:"Time-series",   language:"NoSQL",       tags:"metrics,time-series,iot"})
MERGE (timescaledb:Technology {name:"TimescaleDB",    category:"Database",      domain:"TimeSeries",     type:"Time-series",   language:"SQL",         tags:"metrics,postgres-extension"})
MERGE (clickhouse:Technology  {name:"ClickHouse",     category:"DataWarehouse", domain:"OLAP",           type:"OLAP",          language:"SQL",         tags:"columnar,analytics,fast"})
MERGE (snowflake:Technology   {name:"Snowflake",      category:"DataWarehouse", domain:"DataWarehouse",  type:"Data Warehouse",language:"SQL",         tags:"cloud-dw,analytics,saas"})
MERGE (bigquery:Technology    {name:"BigQuery",       category:"DataWarehouse", domain:"DataWarehouse",  type:"Data Warehouse",language:"SQL",         tags:"cloud-dw,analytics,gcp"})
MERGE (redshift:Technology    {name:"Redshift",       category:"DataWarehouse", domain:"DataWarehouse",  type:"Data Warehouse",language:"SQL",         tags:"cloud-dw,analytics,aws"})
MERGE (supabase:Technology    {name:"Supabase",       category:"Backend",       domain:"BaaS",           type:"BaaS",          language:"SQL",         tags:"postgres,realtime,auth"})
MERGE (pinecone:Technology    {name:"Pinecone",       category:"VectorDB",      domain:"VectorDB",       type:"Vector DB",     language:"NoSQL",       tags:"vector,embeddings,ai"})
MERGE (weaviate:Technology    {name:"Weaviate",       category:"VectorDB",      domain:"VectorDB",       type:"Vector DB",     language:"NoSQL",       tags:"vector,embeddings,ai"})
MERGE (qdrant:Technology      {name:"Qdrant",         category:"VectorDB",      domain:"VectorDB",       type:"Vector DB",     language:"NoSQL",       tags:"vector,embeddings,rust"})
MERGE (chroma:Technology      {name:"ChromaDB",       category:"VectorDB",      domain:"VectorDB",       type:"Vector DB",     language:"NoSQL",       tags:"vector,embeddings,llm"})
MERGE (milvus:Technology      {name:"Milvus",         category:"VectorDB",      domain:"VectorDB",       type:"Vector DB",     language:"NoSQL",       tags:"vector,embeddings,scalable"})

// ── DEVOPS — CONTAINERS & ORCHESTRATION ──────────────────────────────────────
MERGE (docker:Technology      {name:"Docker",         category:"DevOps",        domain:"Container",      type:"Container",     language:"YAML",        tags:"containerization,image,portability"})
MERGE (kubernetes:Technology  {name:"Kubernetes",     category:"DevOps",        domain:"Orchestration",  type:"Orchestration", language:"YAML",        tags:"container-orchestration,k8s,scaling"})
MERGE (helm:Technology        {name:"Helm",           category:"DevOps",        domain:"Orchestration",  type:"Package Mgr",   language:"YAML",        tags:"kubernetes,charts,packaging"})
MERGE (kustomize:Technology   {name:"Kustomize",      category:"DevOps",        domain:"Orchestration",  type:"Config Mgmt",   language:"YAML",        tags:"kubernetes,overlay"})

// ── DEVOPS — IaC & CONFIG MGMT ───────────────────────────────────────────────
MERGE (terraform:Technology   {name:"Terraform",      category:"IaC",           domain:"IaC",            type:"IaC",           language:"HCL",         tags:"infrastructure,provisioning,cloud-agnostic"})
MERGE (pulumi:Technology      {name:"Pulumi",         category:"IaC",           domain:"IaC",            type:"IaC",           language:"TypeScript",  tags:"infrastructure,code-first"})
MERGE (ansible:Technology     {name:"Ansible",        category:"IaC",           domain:"ConfigMgmt",     type:"Config Mgmt",   language:"YAML",        tags:"configuration,agentless,idempotent"})
MERGE (chef:Technology        {name:"Chef",           category:"IaC",           domain:"ConfigMgmt",     type:"Config Mgmt",   language:"Ruby",        tags:"configuration,infrastructure"})
MERGE (puppet:Technology      {name:"Puppet",         category:"IaC",           domain:"ConfigMgmt",     type:"Config Mgmt",   language:"Ruby",        tags:"configuration,declarative"})
MERGE (packer:Technology      {name:"Packer",         category:"IaC",           domain:"IaC",            type:"Image Builder", language:"HCL",         tags:"image-build,ami,immutable"})
MERGE (vagrant:Technology     {name:"Vagrant",        category:"DevOps",        domain:"DevEnv",         type:"DevEnv",        language:"Ruby",        tags:"vm,local-dev"})

// ── DEVOPS — CI/CD & GITOPS ──────────────────────────────────────────────────
MERGE (jenkins:Technology     {name:"Jenkins",        category:"CICD",          domain:"CICD",           type:"CI/CD",         language:"Groovy",      tags:"ci-cd,pipeline,self-hosted"})
MERGE (githubactions:Technology{name:"GitHub Actions",category:"CICD",          domain:"CICD",           type:"CI/CD",         language:"YAML",        tags:"ci-cd,pipeline,github"})
MERGE (gitlabci:Technology    {name:"GitLab CI",      category:"CICD",          domain:"CICD",           type:"CI/CD",         language:"YAML",        tags:"ci-cd,pipeline,gitlab"})
MERGE (circleci:Technology    {name:"CircleCI",       category:"CICD",          domain:"CICD",           type:"CI/CD",         language:"YAML",        tags:"ci-cd,pipeline,cloud"})
MERGE (argocd:Technology      {name:"Argo CD",        category:"CICD",          domain:"GitOps",         type:"GitOps",        language:"YAML",        tags:"gitops,kubernetes,cd"})
MERGE (fluxcd:Technology      {name:"Flux CD",        category:"CICD",          domain:"GitOps",         type:"GitOps",        language:"YAML",        tags:"gitops,kubernetes,cd"})

// ── DEVOPS — OBSERVABILITY ────────────────────────────────────────────────────
MERGE (prometheus:Technology  {name:"Prometheus",     category:"Observability", domain:"Monitoring",     type:"Monitoring",    language:"YAML",        tags:"metrics,alerting,pull-based"})
MERGE (grafana:Technology     {name:"Grafana",        category:"Observability", domain:"Monitoring",     type:"Dashboard",     language:"JSON",        tags:"dashboards,visualization,metrics"})
MERGE (loki:Technology        {name:"Loki",           category:"Observability", domain:"Logging",        type:"Logging",       language:"YAML",        tags:"log-aggregation,grafana"})
MERGE (elk:Technology         {name:"ELK Stack",      category:"Observability", domain:"Logging",        type:"Logging",       language:"YAML",        tags:"elasticsearch,logstash,kibana,logs"})
MERGE (datadog:Technology     {name:"Datadog",        category:"Observability", domain:"APM",            type:"Observability", language:"Agnostic",    tags:"apm,metrics,logs,saas"})
MERGE (newrelic:Technology    {name:"New Relic",      category:"Observability", domain:"APM",            type:"Observability", language:"Agnostic",    tags:"apm,metrics,saas"})
MERGE (opentelemetry:Technology{name:"OpenTelemetry", category:"Observability", domain:"Tracing",        type:"Standard",      language:"Agnostic",    tags:"tracing,metrics,standard"})
MERGE (jaeger:Technology      {name:"Jaeger",         category:"Observability", domain:"Tracing",        type:"Tracing",       language:"Go",          tags:"distributed-tracing,spans"})
MERGE (zipkin:Technology      {name:"Zipkin",         category:"Observability", domain:"Tracing",        type:"Tracing",       language:"Java",        tags:"distributed-tracing,spans"})

// ── DEVOPS — NETWORKING & SERVICE MESH ───────────────────────────────────────
MERGE (nginx:Technology       {name:"Nginx",          category:"DevOps",        domain:"Proxy",          type:"Web Server",    language:"C",           tags:"reverse-proxy,load-balancer,web-server"})
MERGE (traefik:Technology     {name:"Traefik",        category:"DevOps",        domain:"Proxy",          type:"Proxy",         language:"Go",          tags:"reverse-proxy,kubernetes,dynamic"})
MERGE (envoy:Technology       {name:"Envoy",          category:"DevOps",        domain:"ServiceMesh",    type:"Proxy",         language:"C++",         tags:"service-mesh,sidecar,proxy"})
MERGE (istio:Technology       {name:"Istio",          category:"DevOps",        domain:"ServiceMesh",    type:"Service Mesh",  language:"Go",          tags:"service-mesh,mtls,traffic-mgmt"})
MERGE (linkerd:Technology     {name:"Linkerd",        category:"DevOps",        domain:"ServiceMesh",    type:"Service Mesh",  language:"Rust",        tags:"service-mesh,lightweight"})
MERGE (vault:Technology       {name:"HashiCorp Vault",category:"Security",      domain:"Secrets",        type:"Secrets Mgmt",  language:"Go",          tags:"secrets,encryption,pki"})
MERGE (consul:Technology      {name:"Consul",         category:"DevOps",        domain:"ServiceDiscovery",type:"Service Disc", language:"Go",          tags:"service-discovery,config"})

// ── CLOUD PLATFORMS ───────────────────────────────────────────────────────────
MERGE (aws:Technology         {name:"AWS",            category:"Cloud",         domain:"Cloud",          type:"Platform",      language:"Agnostic",    tags:"cloud,iaas,saas,paas"})
MERGE (gcp:Technology         {name:"Google Cloud",   category:"Cloud",         domain:"Cloud",          type:"Platform",      language:"Agnostic",    tags:"cloud,iaas,saas,paas"})
MERGE (azure:Technology       {name:"Azure",          category:"Cloud",         domain:"Cloud",          type:"Platform",      language:"Agnostic",    tags:"cloud,iaas,saas,paas,microsoft"})
MERGE (awslambda:Technology   {name:"AWS Lambda",     category:"Cloud",         domain:"Serverless",     type:"Serverless",    language:"Agnostic",    tags:"serverless,faas,event-driven"})
MERGE (gcpfunctions:Technology{name:"GCP Cloud Func.",category:"Cloud",         domain:"Serverless",     type:"Serverless",    language:"Agnostic",    tags:"serverless,faas,event-driven"})
MERGE (azurefunctions:Technology{name:"Azure Functions",category:"Cloud",       domain:"Serverless",     type:"Serverless",    language:"Agnostic",    tags:"serverless,faas,event-driven"})
MERGE (eks:Technology         {name:"AWS EKS",        category:"Cloud",         domain:"ManagedK8s",     type:"Managed K8s",   language:"YAML",        tags:"kubernetes,managed,aws"})
MERGE (gke:Technology         {name:"GCP GKE",        category:"Cloud",         domain:"ManagedK8s",     type:"Managed K8s",   language:"YAML",        tags:"kubernetes,managed,gcp"})
MERGE (aks:Technology         {name:"Azure AKS",      category:"Cloud",         domain:"ManagedK8s",     type:"Managed K8s",   language:"YAML",        tags:"kubernetes,managed,azure"})
MERGE (cloudflare:Technology  {name:"Cloudflare",     category:"Cloud",         domain:"Edge",           type:"Edge/CDN",      language:"Agnostic",    tags:"cdn,edge,dns,security"})
MERGE (vercel:Technology      {name:"Vercel",         category:"Cloud",         domain:"Hosting",        type:"Hosting",       language:"Agnostic",    tags:"frontend,serverless,nextjs"})
MERGE (netlify:Technology     {name:"Netlify",        category:"Cloud",         domain:"Hosting",        type:"Hosting",       language:"Agnostic",    tags:"frontend,serverless,jamstack"})

// ── MESSAGE BROKERS / STREAMING ───────────────────────────────────────────────
MERGE (kafka:Technology       {name:"Apache Kafka",   category:"MessageBroker", domain:"Streaming",      type:"Event Stream",  language:"Java",        tags:"streaming,pub-sub,high-throughput"})
MERGE (rabbitmq:Technology    {name:"RabbitMQ",       category:"MessageBroker", domain:"Messaging",      type:"Message Broker",language:"Erlang",      tags:"amqp,queue,pub-sub"})
MERGE (nats:Technology        {name:"NATS",           category:"MessageBroker", domain:"Messaging",      type:"Message Broker",language:"Go",          tags:"lightweight,pub-sub,edge"})
MERGE (pulsar:Technology      {name:"Apache Pulsar",  category:"MessageBroker", domain:"Streaming",      type:"Event Stream",  language:"Java",        tags:"streaming,multi-tenant"})
MERGE (sqs:Technology         {name:"AWS SQS",        category:"MessageBroker", domain:"Messaging",      type:"Message Queue", language:"Agnostic",    tags:"managed,queue,aws"})
MERGE (kinesis:Technology     {name:"AWS Kinesis",    category:"MessageBroker", domain:"Streaming",      type:"Event Stream",  language:"Agnostic",    tags:"streaming,real-time,aws"})
MERGE (eventbridge:Technology {name:"AWS EventBridge",category:"MessageBroker", domain:"EventBus",       type:"Event Bus",     language:"Agnostic",    tags:"event-driven,aws,integration"})
MERGE (pubsub:Technology      {name:"GCP Pub/Sub",    category:"MessageBroker", domain:"Messaging",      type:"Message Broker",language:"Agnostic",    tags:"managed,streaming,gcp"})

// ── DATA ENGINEERING ─────────────────────────────────────────────────────────
MERGE (spark:Technology       {name:"Apache Spark",   category:"DataEngineering",domain:"Processing",    type:"Processing",    language:"Scala",       tags:"batch,streaming,distributed"})
MERGE (flink:Technology       {name:"Apache Flink",   category:"DataEngineering",domain:"Processing",    type:"Processing",    language:"Java",        tags:"streaming,real-time,stateful"})
MERGE (airflow:Technology     {name:"Apache Airflow", category:"DataEngineering",domain:"Orchestration", type:"Orchestration", language:"Python",      tags:"workflow,dag,pipeline"})
MERGE (prefect:Technology     {name:"Prefect",        category:"DataEngineering",domain:"Orchestration", type:"Orchestration", language:"Python",      tags:"workflow,dag,pipeline"})
MERGE (dagster:Technology     {name:"Dagster",        category:"DataEngineering",domain:"Orchestration", type:"Orchestration", language:"Python",      tags:"workflow,dag,data-aware"})
MERGE (dbt:Technology         {name:"dbt",            category:"DataEngineering",domain:"Transformation",type:"Transformation",language:"SQL",         tags:"sql-transforms,data-modeling,analytics"})
MERGE (delta_lake:Technology  {name:"Delta Lake",     category:"DataEngineering",domain:"LakeHouse",     type:"Storage Layer", language:"Scala",       tags:"lakehouse,acid,versioning"})
MERGE (iceberg:Technology     {name:"Apache Iceberg", category:"DataEngineering",domain:"LakeHouse",     type:"Table Format",  language:"Java",        tags:"lakehouse,schema-evolution"})
MERGE (dask:Technology        {name:"Dask",           category:"DataEngineering",domain:"Processing",    type:"Library",       language:"Python",      tags:"parallel,pandas-scale"})
MERGE (pandas:Technology      {name:"Pandas",         category:"DataEngineering",domain:"Analysis",      type:"Library",       language:"Python",      tags:"dataframe,analysis,tabular"})
MERGE (polars:Technology      {name:"Polars",         category:"DataEngineering",domain:"Analysis",      type:"Library",       language:"Rust",        tags:"dataframe,fast,lazy-eval"})
MERGE (numpy:Technology       {name:"NumPy",          category:"DataEngineering",domain:"Numerical",     type:"Library",       language:"Python",      tags:"numerical,array,scientific"})
MERGE (scipy:Technology       {name:"SciPy",          category:"DataEngineering",domain:"Numerical",     type:"Library",       language:"Python",      tags:"scientific,statistics,optimization"})

// ── MLOPS ─────────────────────────────────────────────────────────────────────
MERGE (mlflow:Technology      {name:"MLflow",         category:"MLOps",         domain:"Tracking",       type:"Platform",      language:"Python",      tags:"experiment-tracking,model-registry,serving"})
MERGE (kubeflow:Technology    {name:"Kubeflow",       category:"MLOps",         domain:"Pipeline",       type:"Platform",      language:"Python",      tags:"kubernetes,ml-pipeline,training"})
MERGE (bentoml:Technology     {name:"BentoML",        category:"MLOps",         domain:"Serving",        type:"Serving",       language:"Python",      tags:"model-serving,packaging"})
MERGE (seldon:Technology      {name:"Seldon Core",    category:"MLOps",         domain:"Serving",        type:"Serving",       language:"Python",      tags:"model-serving,kubernetes"})
MERGE (kserve:Technology      {name:"KServe",         category:"MLOps",         domain:"Serving",        type:"Serving",       language:"Python",      tags:"model-serving,kubernetes,knative"})
MERGE (torchserve:Technology  {name:"TorchServe",     category:"MLOps",         domain:"Serving",        type:"Serving",       language:"Python",      tags:"model-serving,pytorch"})
MERGE (triton:Technology      {name:"Triton Inference",category:"MLOps",        domain:"Serving",        type:"Serving",       language:"C++",         tags:"model-serving,nvidia,high-throughput"})
MERGE (dvc:Technology         {name:"DVC",            category:"MLOps",         domain:"Versioning",     type:"Versioning",    language:"Python",      tags:"data-version,model-version,git"})
MERGE (wandb:Technology       {name:"Weights & Biases",category:"MLOps",        domain:"Tracking",       type:"Tracking",      language:"Python",      tags:"experiment-tracking,visualization"})
MERGE (neptune:Technology     {name:"Neptune.ai",     category:"MLOps",         domain:"Tracking",       type:"Tracking",      language:"Python",      tags:"experiment-tracking"})
MERGE (evidently:Technology   {name:"Evidently AI",   category:"MLOps",         domain:"Monitoring",     type:"Monitoring",    language:"Python",      tags:"data-drift,model-monitoring"})
MERGE (great_exp:Technology   {name:"Great Expectations",category:"MLOps",      domain:"DataQuality",    type:"Validation",    language:"Python",      tags:"data-quality,testing"})
MERGE (feast:Technology       {name:"Feast",          category:"MLOps",         domain:"FeatureStore",   type:"Feature Store", language:"Python",      tags:"feature-store,ml-platform"})
MERGE (tecton:Technology      {name:"Tecton",         category:"MLOps",         domain:"FeatureStore",   type:"Feature Store", language:"Python",      tags:"feature-store,enterprise"})
MERGE (ray:Technology         {name:"Ray",            category:"MLOps",         domain:"Compute",        type:"Compute",       language:"Python",      tags:"distributed,training,serve"})
MERGE (vertexai:Technology    {name:"Vertex AI",      category:"MLOps",         domain:"ManagedML",      type:"Platform",      language:"Python",      tags:"managed-ml,gcp,training,serving"})
MERGE (sagemaker:Technology   {name:"SageMaker",      category:"MLOps",         domain:"ManagedML",      type:"Platform",      language:"Python",      tags:"managed-ml,aws,training,serving"})
MERGE (azureml:Technology     {name:"Azure ML",       category:"MLOps",         domain:"ManagedML",      type:"Platform",      language:"Python",      tags:"managed-ml,azure,training,serving"})

// ── ML / AI FRAMEWORKS ────────────────────────────────────────────────────────
MERGE (tensorflow:Technology  {name:"TensorFlow",     category:"ML",            domain:"DeepLearning",   type:"Framework",     language:"Python",      tags:"deep-learning,neural-net,google"})
MERGE (pytorch:Technology     {name:"PyTorch",        category:"ML",            domain:"DeepLearning",   type:"Framework",     language:"Python",      tags:"deep-learning,neural-net,dynamic-graph"})
MERGE (jax:Technology         {name:"JAX",            category:"ML",            domain:"DeepLearning",   type:"Framework",     language:"Python",      tags:"autograd,xla,gpu,google"})
MERGE (keras:Technology       {name:"Keras",          category:"ML",            domain:"DeepLearning",   type:"API",           language:"Python",      tags:"high-level,neural-net,tensorflow"})
MERGE (sklearn:Technology     {name:"scikit-learn",   category:"ML",            domain:"ClassicalML",    type:"Library",       language:"Python",      tags:"classical-ml,preprocessing,metrics"})
MERGE (xgboost:Technology     {name:"XGBoost",        category:"ML",            domain:"GradientBoosting",type:"Library",      language:"Python",      tags:"gradient-boosting,tabular,tree"})
MERGE (lightgbm:Technology    {name:"LightGBM",       category:"ML",            domain:"GradientBoosting",type:"Library",      language:"Python",      tags:"gradient-boosting,tabular,fast"})
MERGE (catboost:Technology    {name:"CatBoost",       category:"ML",            domain:"GradientBoosting",type:"Library",      language:"Python",      tags:"gradient-boosting,categorical"})
MERGE (huggingface:Technology {name:"Hugging Face",   category:"ML",            domain:"NLP",            type:"Platform",      language:"Python",      tags:"transformers,model-hub,nlp"})
MERGE (transformers:Technology{name:"HF Transformers",category:"ML",            domain:"NLP",            type:"Library",       language:"Python",      tags:"transformers,bert,gpt,nlp"})
MERGE (diffusers:Technology   {name:"HF Diffusers",   category:"ML",            domain:"GenerativeAI",   type:"Library",       language:"Python",      tags:"diffusion,image-gen,stable-diffusion"})
MERGE (opencv:Technology      {name:"OpenCV",         category:"ML",            domain:"ComputerVision", type:"Library",       language:"C++",         tags:"computer-vision,image-processing"})
MERGE (spacy:Technology       {name:"spaCy",          category:"ML",            domain:"NLP",            type:"Library",       language:"Python",      tags:"nlp,ner,parsing"})
MERGE (nltk:Technology        {name:"NLTK",           category:"ML",            domain:"NLP",            type:"Library",       language:"Python",      tags:"nlp,classical,text"})
MERGE (onnx:Technology        {name:"ONNX",           category:"ML",            domain:"ModelInterop",   type:"Standard",      language:"Agnostic",    tags:"model-interop,export,runtime"})
MERGE (llama_cpp:Technology   {name:"llama.cpp",      category:"ML",            domain:"Inference",      type:"Runtime",       language:"C++",         tags:"llm-inference,local,quantized"})
MERGE (vllm:Technology        {name:"vLLM",           category:"ML",            domain:"Inference",      type:"Runtime",       language:"Python",      tags:"llm-inference,pageattention,gpu"})
MERGE (tgi:Technology         {name:"TGI",            category:"ML",            domain:"Inference",      type:"Runtime",       language:"Python",      tags:"llm-inference,huggingface,serving"})

// ── LLM / AI PRODUCTS & ORCHESTRATION ────────────────────────────────────────
MERGE (openai:Technology      {name:"OpenAI API",     category:"LLM",           domain:"LLMProvider",    type:"API",           language:"Agnostic",    tags:"gpt,llm,embeddings,saas"})
MERGE (anthropic_api:Technology{name:"Anthropic API", category:"LLM",           domain:"LLMProvider",    type:"API",           language:"Agnostic",    tags:"claude,llm,constitutional-ai"})
MERGE (gemini:Technology      {name:"Gemini API",     category:"LLM",           domain:"LLMProvider",    type:"API",           language:"Agnostic",    tags:"llm,multimodal,gcp"})
MERGE (cohere:Technology      {name:"Cohere",         category:"LLM",           domain:"LLMProvider",    type:"API",           language:"Agnostic",    tags:"llm,embeddings,rerank"})
MERGE (mistral:Technology     {name:"Mistral AI",     category:"LLM",           domain:"OpenModel",      type:"Model",         language:"Python",      tags:"open-llm,efficient"})
MERGE (llama:Technology       {name:"LLaMA / Meta AI",category:"LLM",           domain:"OpenModel",      type:"Model",         language:"Python",      tags:"open-llm,meta,foundation"})
MERGE (langchain:Technology   {name:"LangChain",      category:"LLM",           domain:"Orchestration",  type:"Framework",     language:"Python",      tags:"llm-orchestration,chain,rag,agents"})
MERGE (llamaindex:Technology  {name:"LlamaIndex",     category:"LLM",           domain:"RAG",            type:"Framework",     language:"Python",      tags:"rag,indexing,llm-data"})
MERGE (langgraph:Technology   {name:"LangGraph",      category:"LLM",           domain:"Agents",         type:"Framework",     language:"Python",      tags:"agent-graph,stateful-agents"})
MERGE (autogen:Technology     {name:"AutoGen",        category:"LLM",           domain:"Agents",         type:"Framework",     language:"Python",      tags:"multi-agent,microsoft"})
MERGE (crewai:Technology      {name:"CrewAI",         category:"LLM",           domain:"Agents",         type:"Framework",     language:"Python",      tags:"multi-agent,role-based"})
MERGE (dspy:Technology        {name:"DSPy",           category:"LLM",           domain:"Orchestration",  type:"Framework",     language:"Python",      tags:"llm-programming,prompt-optimization"})
MERGE (semantic_kernel:Technology{name:"Semantic Kernel",category:"LLM",        domain:"Orchestration",  type:"Framework",     language:"C#",          tags:"llm-orchestration,microsoft,plugins"})
MERGE (promptflow:Technology  {name:"Prompt Flow",    category:"LLM",           domain:"LLMOps",         type:"Platform",      language:"Python",      tags:"llm-ops,azure,pipeline"})
MERGE (litellm:Technology     {name:"LiteLLM",        category:"LLM",           domain:"Gateway",        type:"Library",       language:"Python",      tags:"llm-gateway,multi-provider"})
MERGE (guardrails:Technology  {name:"Guardrails AI",  category:"LLM",           domain:"Safety",         type:"Library",       language:"Python",      tags:"llm-safety,validation,output"})

// ── CYBERSECURITY ─────────────────────────────────────────────────────────────
MERGE (burpsuite:Technology   {name:"Burp Suite",     category:"Security",      domain:"PenTest",        type:"Tool",          language:"Java",        tags:"web-pentest,proxy,scanner"})
MERGE (nmap:Technology        {name:"Nmap",           category:"Security",      domain:"Recon",          type:"Tool",          language:"C",           tags:"network-scan,discovery"})
MERGE (metasploit:Technology  {name:"Metasploit",     category:"Security",      domain:"PenTest",        type:"Framework",     language:"Ruby",        tags:"pentest,exploit,redteam"})
MERGE (wireshark:Technology   {name:"Wireshark",      category:"Security",      domain:"Recon",          type:"Tool",          language:"C",           tags:"packet-capture,network-analysis"})
MERGE (snort:Technology       {name:"Snort/Suricata", category:"Security",      domain:"IDS",            type:"IDS/IPS",       language:"C",           tags:"intrusion-detection,network"})
MERGE (ossec:Technology       {name:"Wazuh/OSSEC",    category:"Security",      domain:"SIEM",           type:"SIEM",          language:"C",           tags:"siem,hids,compliance"})
MERGE (splunk:Technology      {name:"Splunk",         category:"Security",      domain:"SIEM",           type:"SIEM",          language:"Python",      tags:"siem,log-analysis,threat-hunting"})
MERGE (crowdstrike:Technology {name:"CrowdStrike",    category:"Security",      domain:"EDR",            type:"EDR",           language:"Agnostic",    tags:"edr,endpoint,threat-intel"})
MERGE (owasp:Technology       {name:"OWASP ZAP",      category:"Security",      domain:"DAST",           type:"Scanner",       language:"Java",        tags:"web-scanner,dast,pentest"})
MERGE (sonarqube:Technology   {name:"SonarQube",      category:"Security",      domain:"SAST",           type:"SAST",          language:"Java",        tags:"code-quality,sast,static-analysis"})
MERGE (trivy:Technology       {name:"Trivy",          category:"Security",      domain:"CSPM",           type:"Scanner",       language:"Go",          tags:"container-scan,vuln,sbom"})
MERGE (falco:Technology       {name:"Falco",          category:"Security",      domain:"RuntimeSec",     type:"Runtime Sec",   language:"C++",         tags:"runtime-security,kubernetes,syscall"})
MERGE (opa:Technology         {name:"OPA",            category:"Security",      domain:"PolicyAsCode",   type:"Policy",        language:"Rego",        tags:"policy-as-code,authorization,kubernetes"})
MERGE (keycloak:Technology    {name:"Keycloak",       category:"Security",      domain:"IAM",            type:"IAM",           language:"Java",        tags:"oidc,oauth2,sso,identity"})
MERGE (oauth2:Technology      {name:"OAuth 2.0",      category:"Security",      domain:"AuthProtocol",   type:"Protocol",      language:"Agnostic",    tags:"authorization,token,identity"})
MERGE (jwt:Technology         {name:"JWT",            category:"Security",      domain:"AuthStandard",   type:"Standard",      language:"Agnostic",    tags:"auth-token,stateless,claims"})

// ── MOBILE ────────────────────────────────────────────────────────────────────
MERGE (reactnative:Technology {name:"React Native",   category:"Mobile",        domain:"CrossPlatform",  type:"Framework",     language:"JavaScript",  tags:"cross-platform,ios,android"})
MERGE (flutter:Technology     {name:"Flutter",        category:"Mobile",        domain:"CrossPlatform",  type:"Framework",     language:"Dart",        tags:"cross-platform,ios,android,ui"})
MERGE (swift:Technology       {name:"Swift",          category:"Mobile",        domain:"iOS",            type:"Language",      language:"Swift",       tags:"ios,macos,native"})
MERGE (kotlin_android:Technology{name:"Kotlin Android",category:"Mobile",       domain:"Android",        type:"Language",      language:"Kotlin",      tags:"android,native,jvm"})
MERGE (ionic:Technology       {name:"Ionic",          category:"Mobile",        domain:"CrossPlatform",  type:"Framework",     language:"TypeScript",  tags:"hybrid,web-based,cross-platform"})
MERGE (capacitor:Technology   {name:"Capacitor",      category:"Mobile",        domain:"CrossPlatform",  type:"Runtime",       language:"TypeScript",  tags:"hybrid,web-to-native"})
MERGE (expo:Technology        {name:"Expo",           category:"Mobile",        domain:"CrossPlatform",  type:"Platform",      language:"JavaScript",  tags:"react-native,managed,eas"})

// ─────────────────────────────────────────────────────────────────────────────
// 2. RELATIONSHIP DEFINITIONS
// Focus: knowledge transferability and necessary co-usage
// ─────────────────────────────────────────────────────────────────────────────

// ════════════════════════════════════════
// FRONTEND — TRANSFERABILITY
// ════════════════════════════════════════
// Component-model skills transfer across all three
MERGE (react)-[:TRANSFERABLE_TO    {reason:"Both use component-based architecture; JSX patterns, lifecycle and state hooks transfer directly", weight:0.85}]->(vue)
MERGE (react)-[:TRANSFERABLE_TO    {reason:"Component thinking, unidirectional data flow and SPA routing patterns transfer; Angular adds strong DI patterns", weight:0.75}]->(angular)
MERGE (vue)-[:TRANSFERABLE_TO      {reason:"Reactive component model and template syntax transfer; React differs in JSX style", weight:0.80}]->(react)
MERGE (angular)-[:TRANSFERABLE_TO  {reason:"DI and service patterns transfer; React has no equivalent but component model is shared", weight:0.72}]->(react)
MERGE (svelte)-[:TRANSFERABLE_TO   {reason:"Component structure and reactive state concepts transfer; compile-time paradigm is unique to Svelte", weight:0.75}]->(react)
MERGE (solidjs)-[:TRANSFERABLE_TO  {reason:"JSX syntax and fine-grained reactivity signal concepts transfer to React hooks understanding", weight:0.78}]->(react)

// SSR meta-frameworks
MERGE (nextjs)-[:EQUIVALENT_IN     {reason:"Both are the SSR/SSG meta-framework for their base UI library; all routing/loader patterns are equivalent", weight:0.95}]->(nuxtjs)
MERGE (nextjs)-[:TRANSFERABLE_TO   {reason:"File-based routing, data loaders and server actions patterns transfer significantly between the two React SSR frameworks", weight:0.82}]->(remix)
MERGE (nextjs)-[:REQUIRES          {reason:"Next.js is a React meta-framework; React knowledge is mandatory", weight:1.0}]->(react)
MERGE (nuxtjs)-[:REQUIRES          {reason:"Nuxt.js is a Vue meta-framework; Vue knowledge is mandatory", weight:1.0}]->(vue)
MERGE (remix)-[:REQUIRES           {reason:"Remix is a React framework; React knowledge is mandatory", weight:1.0}]->(react)
MERGE (gatsby)-[:REQUIRES          {reason:"Gatsby is React-based; React is a hard dependency", weight:1.0}]->(react)
MERGE (gatsby)-[:TRANSFERABLE_TO   {reason:"Static site generation, GraphQL data layer and island hydration patterns transfer to Astro", weight:0.70}]->(astro)
MERGE (nextjs)-[:OFTEN_USED_WITH   {reason:"Next.js apps are commonly deployed on Vercel's edge network", weight:0.85}]->(vercel)

// Build tools transferability
MERGE (webpack)-[:TRANSFERABLE_TO  {reason:"Module graph, loaders and plugin concepts transfer; Vite uses a different dev server but builds on the same mental model", weight:0.75}]->(vite)
MERGE (vite)-[:EVOLVED_INTO        {reason:"Vite supersedes Webpack as the default dev server for modern frontend stacks", weight:0.90}]->(webpack)
MERGE (turbopack)-[:EVOLVED_INTO   {reason:"Turbopack is the Rust-based Webpack successor built by the Vercel/webpack author", weight:0.85}]->(webpack)
MERGE (turbopack)-[:TRANSFERABLE_TO{reason:"Both are Rust-based fast bundlers; esbuild concepts transfer", weight:0.80}]->(esbuild)
MERGE (esbuild)-[:TRANSFERABLE_TO  {reason:"Fast bundling and tree-shaking concepts transfer; Vite uses esbuild internally", weight:0.82}]->(vite)
MERGE (rollup)-[:TRANSFERABLE_TO   {reason:"Tree-shaking, ESM output and plugin API patterns transfer; Rollup powers Vite's production builds", weight:0.80}]->(vite)
MERGE (vite)-[:REQUIRES            {reason:"Vite production builds run on Rollup; Rollup knowledge helps debug output", weight:0.70}]->(rollup)
MERGE (vite)-[:OFTEN_USED_WITH     {reason:"Vitest is the natural test runner companion for Vite projects", weight:0.92}]->(vitest)

// Testing transferability
MERGE (jest)-[:TRANSFERABLE_TO     {reason:"Vitest is a drop-in Jest replacement; all test/mock/spy APIs are identical by design", weight:0.97}]->(vitest)
MERGE (vitest)-[:TRANSFERABLE_TO   {reason:"Jest and Vitest share the same API surface; skills are almost fully interchangeable", weight:0.97}]->(jest)
MERGE (cypress)-[:TRANSFERABLE_TO  {reason:"E2E selector, assertion and async wait patterns transfer; Playwright uses the same concepts with a slightly different API", weight:0.82}]->(playwright)
MERGE (playwright)-[:EVOLVED_INTO  {reason:"Playwright is the community-preferred successor to Cypress for cross-browser E2E testing", weight:0.80}]->(cypress)

// State management
MERGE (redux)-[:TRANSFERABLE_TO    {reason:"Flux unidirectional data flow and action/reducer patterns transfer; Zustand is a simpler version of the same idea", weight:0.80}]->(zustand)
MERGE (zustand)-[:TRANSFERABLE_TO  {reason:"Simple store and subscriber patterns transfer to MobX reactive stores", weight:0.72}]->(mobx)
MERGE (pinia)-[:EQUIVALENT_IN      {reason:"Pinia is to Vue what Zustand/Redux is to React — same store pattern, Vue ecosystem", weight:0.90}]->(zustand)
MERGE (redux)-[:OFTEN_USED_WITH    {reason:"Redux is the standard companion state manager for large React apps", weight:0.85}]->(react)
MERGE (pinia)-[:REQUIRES           {reason:"Pinia is the official Vue state manager and requires Vue", weight:0.95}]->(vue)
MERGE (reactquery)-[:TRANSFERABLE_TO{reason:"Server-state caching, stale-while-revalidate and query-key patterns transfer between React Query and Apollo Client", weight:0.78}]->(apollo)
MERGE (apollo)-[:REQUIRES          {reason:"Apollo Client manages GraphQL queries; GraphQL schema knowledge is required", weight:0.90}]->(graphql)

// CSS / UI
MERGE (tailwind)-[:TRANSFERABLE_TO {reason:"Utility-first CSS thinking and responsive modifier syntax transfer; Bootstrap uses component-class approach instead", weight:0.65}]->(bootstrap)
MERGE (bootstrap)-[:TRANSFERABLE_TO{reason:"Responsive grid system and component naming conventions inform Tailwind usage", weight:0.60}]->(tailwind)
MERGE (shadcn)-[:REQUIRES          {reason:"shadcn/ui components are built with and require Tailwind CSS", weight:1.0}]->(tailwind)
MERGE (shadcn)-[:REQUIRES          {reason:"shadcn/ui is a React component library; React is required", weight:1.0}]->(react)
MERGE (materialui)-[:REQUIRES      {reason:"Material UI is a React-specific component library", weight:1.0}]->(react)
MERGE (materialui)-[:TRANSFERABLE_TO{reason:"Design system thinking and component API patterns transfer between React UI libraries", weight:0.78}]->(shadcn)

// Language
MERGE (typescript)-[:EXTENDS       {reason:"TypeScript is a typed superset of JavaScript; all JS code is valid TS", weight:1.0}]->(javascript)
MERGE (javascript)-[:TRANSFERABLE_TO{reason:"JavaScript is the runtime of TypeScript; JS knowledge is directly required to use TS effectively", weight:0.95}]->(typescript)
MERGE (typescript)-[:OFTEN_USED_WITH{reason:"TypeScript is the recommended language for all Angular projects by default", weight:0.98}]->(angular)
MERGE (typescript)-[:OFTEN_USED_WITH{reason:"TypeScript is the primary language for NestJS, adding type safety to the backend", weight:0.95}]->(nestjs)
MERGE (rxjs)-[:OFTEN_USED_WITH     {reason:"RxJS is Angular's core reactive primitive; Observable patterns are used everywhere in Angular", weight:0.95}]->(angular)

// ════════════════════════════════════════
// BACKEND — TRANSFERABILITY
// ════════════════════════════════════════
// Node.js ecosystem
MERGE (nodejs)-[:OFTEN_USED_WITH   {reason:"Express is the default HTTP framework run on the Node.js runtime", weight:0.90}]->(express)
MERGE (nodejs)-[:OFTEN_USED_WITH   {reason:"Fastify runs on Node.js and is a direct Express alternative", weight:0.85}]->(fastify)
MERGE (nodejs)-[:OFTEN_USED_WITH   {reason:"NestJS compiles to Node.js and uses it as its runtime", weight:0.90}]->(nestjs)
MERGE (express)-[:TRANSFERABLE_TO  {reason:"Middleware chain, routing and req/res patterns are identical; Fastify extends the same ideas with better perf and schema validation", weight:0.90}]->(fastify)
MERGE (fastify)-[:TRANSFERABLE_TO  {reason:"Fastify's route-handler and plugin patterns are the basis of Hono's API design", weight:0.80}]->(hono)
MERGE (express)-[:TRANSFERABLE_TO  {reason:"Middleware, routing and controller patterns transfer; NestJS adds DI and decorators on top", weight:0.75}]->(nestjs)
MERGE (nestjs)-[:EQUIVALENT_IN     {reason:"NestJS (Node.js) and Spring Boot (Java) both provide an opinionated DI+decorator enterprise backend framework", weight:0.88}]->(springboot)

// Python ecosystem
MERGE (flask)-[:TRANSFERABLE_TO    {reason:"Route decorators, request context and WSGI app patterns transfer directly; FastAPI adds async and type hints", weight:0.85}]->(fastapi)
MERGE (fastapi)-[:TRANSFERABLE_TO  {reason:"Python route decorator style and ORM integration patterns transfer; Django adds a full ORM and admin", weight:0.72}]->(django)
MERGE (fastapi)-[:REQUIRES         {reason:"FastAPI relies on Python type hints and Pydantic for request validation; Python and Pydantic are hard dependencies", weight:0.95}]->(python)
MERGE (django)-[:REQUIRES          {reason:"Django is a Python framework; Python is required", weight:1.0}]->(python)
MERGE (flask)-[:REQUIRES           {reason:"Flask is a Python micro-framework; Python is required", weight:1.0}]->(python)

// JVM family
MERGE (java)-[:TRANSFERABLE_TO     {reason:"Kotlin is 100% interoperable with Java; Java knowledge transfers almost entirely to Kotlin", weight:0.92}]->(kotlin)
MERGE (kotlin)-[:EVOLVED_INTO      {reason:"Kotlin is the modern JVM language that supersedes Java for most new JVM projects", weight:0.90}]->(java)
MERGE (java)-[:TRANSFERABLE_TO     {reason:"OOP and JVM runtime knowledge transfers; Scala adds functional programming paradigm", weight:0.70}]->(scala)
MERGE (scala)-[:TRANSFERABLE_TO    {reason:"JVM knowledge and some OOP patterns transfer back; Scala functional idioms are advanced", weight:0.65}]->(java)
MERGE (springboot)-[:REQUIRES      {reason:"Spring Boot is a Java framework; Java (or Kotlin) knowledge is required", weight:1.0}]->(java)
MERGE (ktor)-[:REQUIRES            {reason:"Ktor is Kotlin-native; Kotlin is required", weight:1.0}]->(kotlin)
MERGE (quarkus)-[:TRANSFERABLE_TO  {reason:"Both are cloud-native JVM frameworks with DI and reactive patterns; Spring Boot knowledge transfers significantly", weight:0.85}]->(micronaut)
MERGE (quarkus)-[:TRANSFERABLE_TO  {reason:"Spring Boot concepts (DI, REST, JPA) transfer; Quarkus adds native compilation", weight:0.82}]->(springboot)
MERGE (akka)-[:REQUIRES            {reason:"Akka is a Scala/JVM actor framework; Scala and JVM are required", weight:0.90}]->(scala)

// Go ecosystem
MERGE (gin)-[:TRANSFERABLE_TO      {reason:"Router, handler and middleware patterns are nearly identical between Gin and Fiber", weight:0.92}]->(fiber)
MERGE (fiber)-[:EQUIVALENT_IN      {reason:"Fiber replicates Express.js's API in Go; Express knowledge transfers directly", weight:0.88}]->(express)
MERGE (gin)-[:EQUIVALENT_IN        {reason:"Gin fills the same minimal HTTP router role as Flask/Express but in Go", weight:0.82}]->(flask)
MERGE (gin)-[:REQUIRES             {reason:"Gin is a Go web framework; Go language knowledge is required", weight:1.0}]->(golang)
MERGE (fiber)-[:REQUIRES           {reason:"Fiber is a Go web framework; Go language knowledge is required", weight:1.0}]->(golang)

// Rust ecosystem
MERGE (actix)-[:TRANSFERABLE_TO    {reason:"Actor model and async handler patterns transfer; Axum is the more ergonomic Tower-native alternative", weight:0.85}]->(axum)
MERGE (axum)-[:REQUIRES            {reason:"Axum is built on Tokio async runtime; Rust and Tokio knowledge are required", weight:0.95}]->(rust)
MERGE (actix)-[:REQUIRES           {reason:"Actix-web is a Rust framework; Rust knowledge is required", weight:1.0}]->(rust)

// .NET / C#
MERGE (dotnet)-[:REQUIRES          {reason:"ASP.NET is the C# web framework; C# knowledge is required", weight:1.0}]->(csharp)
MERGE (dotnet)-[:EQUIVALENT_IN     {reason:"ASP.NET and Spring Boot both provide enterprise-grade DI, REST and middleware pipeline in their respective ecosystems", weight:0.88}]->(springboot)

// PHP ecosystem
MERGE (laravel)-[:EQUIVALENT_IN    {reason:"Laravel (PHP) and Rails (Ruby) are both MVC convention-over-config full-stack frameworks with similar feature sets", weight:0.92}]->(rails)
MERGE (symfony)-[:TRANSFERABLE_TO  {reason:"Symfony components (routing, DI container, HTTP kernel) are the foundation of Laravel; Symfony knowledge transfers to Laravel", weight:0.85}]->(laravel)
MERGE (laravel)-[:REQUIRES         {reason:"Laravel is a PHP framework; PHP is required", weight:1.0}]->(php)
MERGE (symfony)-[:REQUIRES         {reason:"Symfony is a PHP framework; PHP is required", weight:1.0}]->(php)

// Ruby / Elixir
MERGE (rails)-[:EQUIVALENT_IN      {reason:"Rails (Ruby) and Django (Python) are both batteries-included MVC web frameworks with ORM, migrations and admin", weight:0.88}]->(django)
MERGE (rails)-[:REQUIRES           {reason:"Rails is a Ruby framework; Ruby is required", weight:1.0}]->(ruby)
MERGE (phoenix)-[:TRANSFERABLE_TO  {reason:"MVC conventions and router/controller/view patterns transfer from Rails to Phoenix; Elixir concurrency model is different", weight:0.78}]->(rails)
MERGE (phoenix)-[:REQUIRES         {reason:"Phoenix is an Elixir framework; Elixir and OTP knowledge are required", weight:1.0}]->(elixir)

// API patterns
MERGE (rest)-[:TRANSFERABLE_TO     {reason:"HTTP verbs, stateless request model and resource design patterns are foundational knowledge that transfers to GraphQL API design", weight:0.72}]->(graphql)
MERGE (graphql)-[:TRANSFERABLE_TO  {reason:"Schema-first thinking and typed contract design transfer; gRPC uses Protobuf instead of SDL", weight:0.65}]->(grpc)
MERGE (trpc)-[:REQUIRES            {reason:"tRPC is TypeScript-only and requires both a Node.js backend and TypeScript frontend", weight:0.95}]->(typescript)
MERGE (trpc)-[:BRIDGES             {reason:"tRPC eliminates the REST/GraphQL layer by sharing TypeScript types end-to-end between Next.js/Node backend and frontend", weight:0.92}]->(nodejs)
MERGE (graphqlserver)-[:OFTEN_USED_WITH{reason:"Apollo Server is the most common GraphQL server implementation", weight:0.88}]->(apollo)
MERGE (swagger)-[:OFTEN_USED_WITH  {reason:"FastAPI auto-generates OpenAPI/Swagger docs from Python type hints", weight:0.92}]->(fastapi)
MERGE (swagger)-[:OFTEN_USED_WITH  {reason:"Swagger/OpenAPI is used alongside REST APIs for documentation and client generation", weight:0.85}]->(rest)
MERGE (postman)-[:OFTEN_USED_WITH  {reason:"Postman is the standard tool for testing REST APIs during development", weight:0.85}]->(rest)
MERGE (kong)-[:TRANSFERABLE_TO     {reason:"API gateway concepts (rate limiting, auth plugins, routing) transfer between Kong and Traefik", weight:0.75}]->(traefik)
MERGE (kong)-[:TRANSFERABLE_TO     {reason:"API management concepts transfer from Kong to Apigee; Apigee adds enterprise analytics", weight:0.72}]->(apigee)
MERGE (aws_apigw)-[:EQUIVALENT_IN  {reason:"AWS API Gateway and Kong both fulfil the API gateway role; skills transfer across the two", weight:0.82}]->(kong)

// ════════════════════════════════════════
// DATABASES — TRANSFERABILITY
// ════════════════════════════════════════
MERGE (postgres)-[:TRANSFERABLE_TO {reason:"Standard SQL, ACID transactions and index design transfer fully; syntax differences are minor", weight:0.88}]->(mysql)
MERGE (mysql)-[:TRANSFERABLE_TO    {reason:"SQL DML/DDL, index and join knowledge transfers; Postgres has richer types and extensions", weight:0.85}]->(postgres)
MERGE (mssql)-[:TRANSFERABLE_TO    {reason:"T-SQL and enterprise RDBMS administration skills transfer; syntax dialect differs", weight:0.82}]->(oracle)
MERGE (oracle)-[:TRANSFERABLE_TO   {reason:"PL/SQL patterns and enterprise tuning knowledge transfer to SQL Server", weight:0.80}]->(mssql)
MERGE (sqlite)-[:TRANSFERABLE_TO   {reason:"SQLite uses standard SQL; skills transfer fully to Postgres or MySQL", weight:0.88}]->(postgres)
MERGE (timescaledb)-[:EXTENDS      {reason:"TimescaleDB is a Postgres extension; all Postgres knowledge applies plus time-series functions", weight:1.0}]->(postgres)
MERGE (supabase)-[:EXTENDS         {reason:"Supabase is a BaaS wrapper around Postgres; PostgreSQL knowledge is fully reused", weight:0.95}]->(postgres)

MERGE (mongodb)-[:TRANSFERABLE_TO  {reason:"Document model, aggregation pipeline and index design transfer; CouchDB uses HTTP API instead of drivers", weight:0.80}]->(couchdb)
MERGE (mongodb)-[:TRANSFERABLE_TO  {reason:"Document model and JSON query patterns transfer; DynamoDB has a different access pattern philosophy", weight:0.65}]->(dynamodb)
MERGE (firestore)-[:EQUIVALENT_IN  {reason:"Both are managed cloud document stores with realtime listeners; Firestore is GCP, DynamoDB is AWS", weight:0.82}]->(dynamodb)

MERGE (elasticsearch)-[:TRANSFERABLE_TO{reason:"OpenSearch is a fork of Elasticsearch 7.x; all query DSL, mapping and cluster management skills transfer 1:1", weight:0.98}]->(opensearch)
MERGE (opensearch)-[:EVOLVED_INTO  {reason:"OpenSearch forked from Elasticsearch and is now its open-source successor in many stacks", weight:0.95}]->(elasticsearch)

MERGE (redis)-[:TRANSFERABLE_TO    {reason:"In-memory key-value storage and TTL-based cache patterns transfer; Redis offers richer data structures", weight:0.75}]->(memcached)
MERGE (redis)-[:BRIDGES            {reason:"Redis is used both as an application cache and as a lightweight pub/sub message broker", weight:0.82}]->(rabbitmq)

MERGE (cassandra)-[:TRANSFERABLE_TO{reason:"CQL (Cassandra Query Language) and wide-column data modelling skills transfer directly; ScyllaDB is a drop-in binary replacement", weight:0.97}]->(scylladb)
MERGE (scylladb)-[:EVOLVED_INTO    {reason:"ScyllaDB re-implements Cassandra in C++ for higher throughput; Cassandra skills transfer fully", weight:0.97}]->(cassandra)

MERGE (influxdb)-[:TRANSFERABLE_TO {reason:"Time-series data modelling and retention policy concepts transfer; TimescaleDB uses standard SQL instead of InfluxQL", weight:0.72}]->(timescaledb)

MERGE (snowflake)-[:TRANSFERABLE_TO{reason:"Cloud DW SQL dialect and data sharing concepts transfer; BigQuery uses standard SQL", weight:0.85}]->(bigquery)
MERGE (bigquery)-[:TRANSFERABLE_TO {reason:"Cloud DW columnar query patterns and partitioning strategies transfer to Redshift", weight:0.85}]->(redshift)
MERGE (clickhouse)-[:TRANSFERABLE_TO{reason:"Columnar OLAP query patterns, materialized views and partitioning skills transfer to BigQuery and Redshift", weight:0.78}]->(bigquery)
MERGE (dbt)-[:OFTEN_USED_WITH      {reason:"dbt is the standard SQL transformation layer used on top of cloud data warehouses", weight:0.92}]->(snowflake)
MERGE (dbt)-[:OFTEN_USED_WITH      {reason:"dbt models compile directly to BigQuery SQL", weight:0.90}]->(bigquery)
MERGE (dbt)-[:OFTEN_USED_WITH      {reason:"dbt models compile directly to Redshift SQL", weight:0.88}]->(redshift)

MERGE (neo4j)-[:TRANSFERABLE_TO    {reason:"Graph data modelling, Cypher query language and traversal thinking transfer to TigerGraph GSQL", weight:0.75}]->(tigergraph)

MERGE (pinecone)-[:TRANSFERABLE_TO {reason:"Vector index creation, embedding upsert and similarity search API patterns transfer across vector DBs", weight:0.90}]->(weaviate)
MERGE (weaviate)-[:TRANSFERABLE_TO {reason:"Vector search, filter and hybrid-search patterns transfer; Qdrant uses a different filter syntax", weight:0.88}]->(qdrant)
MERGE (qdrant)-[:TRANSFERABLE_TO   {reason:"Lightweight vector store concepts and collection API patterns transfer to ChromaDB", weight:0.85}]->(chroma)
MERGE (milvus)-[:TRANSFERABLE_TO   {reason:"Scalable vector indexing and partition strategies transfer to Pinecone and Weaviate", weight:0.80}]->(pinecone)
MERGE (pinecone)-[:OFTEN_USED_WITH {reason:"Pinecone is the most common vector store plugged into LangChain RAG pipelines", weight:0.90}]->(langchain)
MERGE (qdrant)-[:OFTEN_USED_WITH   {reason:"Qdrant is a popular open-source vector store used with LangChain and LlamaIndex", weight:0.88}]->(langchain)
MERGE (weaviate)-[:OFTEN_USED_WITH {reason:"Weaviate integrates natively with LangChain and LlamaIndex for RAG", weight:0.85}]->(langchain)
MERGE (chroma)-[:OFTEN_USED_WITH   {reason:"ChromaDB is the default local vector store for LangChain and LlamaIndex examples", weight:0.90}]->(llamaindex)

// ════════════════════════════════════════
// DEVOPS — TRANSFERABILITY
// ════════════════════════════════════════
MERGE (docker)-[:OFTEN_USED_WITH   {reason:"Docker is the container runtime that Kubernetes orchestrates; Docker knowledge is a prerequisite for K8s", weight:0.98}]->(kubernetes)
MERGE (docker)-[:REQUIRES          {reason:"Kubernetes orchestrates Docker (or OCI) containers; understanding images and container lifecycle is required", weight:0.95}]->(kubernetes)
MERGE (kubernetes)-[:OFTEN_USED_WITH{reason:"Helm is the standard package manager for deploying applications on Kubernetes", weight:0.92}]->(helm)
MERGE (kubernetes)-[:OFTEN_USED_WITH{reason:"Kustomize is built into kubectl and used to patch K8s YAML without templating", weight:0.82}]->(kustomize)
MERGE (helm)-[:REQUIRES            {reason:"Helm packages and deploys Kubernetes manifests; K8s knowledge is required to use Helm effectively", weight:0.95}]->(kubernetes)
MERGE (kustomize)-[:REQUIRES       {reason:"Kustomize overlays are applied on top of Kubernetes manifests; K8s knowledge is required", weight:0.95}]->(kubernetes)

MERGE (eks)-[:EQUIVALENT_IN        {reason:"EKS, GKE and AKS all provide managed Kubernetes; skills transfer completely across the three", weight:0.97}]->(gke)
MERGE (gke)-[:EQUIVALENT_IN        {reason:"EKS, GKE and AKS all provide managed Kubernetes; skills transfer completely across the three", weight:0.97}]->(aks)
MERGE (eks)-[:REQUIRES             {reason:"EKS is AWS-managed Kubernetes; Kubernetes and AWS knowledge are both required", weight:0.95}]->(kubernetes)
MERGE (gke)-[:REQUIRES             {reason:"GKE is GCP-managed Kubernetes; Kubernetes and GCP knowledge are both required", weight:0.95}]->(kubernetes)
MERGE (aks)-[:REQUIRES             {reason:"AKS is Azure-managed Kubernetes; Kubernetes and Azure knowledge are both required", weight:0.95}]->(kubernetes)

MERGE (terraform)-[:TRANSFERABLE_TO{reason:"Declarative infrastructure, state management and provider concepts transfer; Pulumi uses real programming languages instead of HCL", weight:0.82}]->(pulumi)
MERGE (pulumi)-[:TRANSFERABLE_TO   {reason:"Cloud resource and state management thinking transfers back; Terraform uses HCL instead of code", weight:0.80}]->(terraform)
MERGE (packer)-[:OFTEN_USED_WITH   {reason:"Packer builds machine images that are provisioned and deployed by Terraform", weight:0.85}]->(terraform)
MERGE (packer)-[:TRANSFERABLE_TO   {reason:"Packer builder configuration patterns transfer; Ansible is often called within Packer builds", weight:0.72}]->(ansible)

MERGE (ansible)-[:TRANSFERABLE_TO  {reason:"Idempotent task-runner and inventory concepts transfer; Chef uses Ruby DSL and pull model instead", weight:0.72}]->(chef)
MERGE (ansible)-[:TRANSFERABLE_TO  {reason:"Declarative configuration management mindset transfers; Puppet uses its own DSL", weight:0.72}]->(puppet)
MERGE (chef)-[:TRANSFERABLE_TO     {reason:"Both use Ruby DSL and cookbook/manifest concepts; skills transfer between the two", weight:0.85}]->(puppet)

MERGE (githubactions)-[:TRANSFERABLE_TO{reason:"YAML pipeline steps, environment variables and artifact handling patterns transfer; GitLab CI has a slightly different syntax", weight:0.85}]->(gitlabci)
MERGE (gitlabci)-[:TRANSFERABLE_TO {reason:"Pipeline stage/job concepts and runner configuration transfer to GitHub Actions workflows", weight:0.83}]->(githubactions)
MERGE (jenkins)-[:TRANSFERABLE_TO  {reason:"Pipeline stage and step concepts transfer; Jenkins uses Groovy/Jenkinsfile while GitHub Actions uses YAML", weight:0.70}]->(githubactions)
MERGE (argocd)-[:TRANSFERABLE_TO   {reason:"GitOps reconciliation loop and application sync model transfer; Flux is more Helm-native", weight:0.88}]->(fluxcd)
MERGE (argocd)-[:REQUIRES          {reason:"Argo CD syncs applications onto Kubernetes; K8s knowledge is required", weight:0.95}]->(kubernetes)
MERGE (fluxcd)-[:REQUIRES          {reason:"Flux CD reconciles Kubernetes manifests; K8s knowledge is required", weight:0.95}]->(kubernetes)

MERGE (istio)-[:REQUIRES           {reason:"Istio deploys as sidecar containers in Kubernetes pods; K8s knowledge is required", weight:0.95}]->(kubernetes)
MERGE (istio)-[:REQUIRES           {reason:"Istio's data plane is Envoy; understanding Envoy's xDS API is necessary for advanced Istio configuration", weight:0.85}]->(envoy)
MERGE (linkerd)-[:REQUIRES         {reason:"Linkerd is a Kubernetes-native service mesh; K8s knowledge is required", weight:0.95}]->(kubernetes)
MERGE (istio)-[:TRANSFERABLE_TO    {reason:"mTLS, traffic management and observability sidecar concepts transfer between the two service meshes", weight:0.82}]->(linkerd)
MERGE (envoy)-[:TRANSFERABLE_TO    {reason:"L7 proxy, route matching and filter chain concepts transfer to Traefik's middleware model", weight:0.75}]->(traefik)
MERGE (nginx)-[:TRANSFERABLE_TO    {reason:"Reverse proxy, virtual host and upstream configuration patterns transfer to Traefik", weight:0.78}]->(traefik)

MERGE (prometheus)-[:OFTEN_USED_WITH{reason:"Grafana is the standard dashboard UI for Prometheus metrics", weight:0.97}]->(grafana)
MERGE (loki)-[:OFTEN_USED_WITH     {reason:"Loki is designed to integrate with Grafana for log visualization alongside Prometheus metrics", weight:0.95}]->(grafana)
MERGE (opentelemetry)-[:BRIDGES    {reason:"OpenTelemetry collects traces, metrics and logs from application code and exports them to Jaeger, Prometheus and Grafana", weight:0.92}]->(prometheus)
MERGE (opentelemetry)-[:OFTEN_USED_WITH{reason:"Jaeger is a primary OTLP-compatible tracing backend for OpenTelemetry", weight:0.90}]->(jaeger)
MERGE (jaeger)-[:TRANSFERABLE_TO   {reason:"Span, trace and sampling concepts are identical; both implement the OpenTracing standard", weight:0.92}]->(zipkin)
MERGE (datadog)-[:TRANSFERABLE_TO  {reason:"APM, metric dashboards and log correlation concepts transfer; New Relic is a similar commercial platform", weight:0.85}]->(newrelic)
MERGE (elk)-[:TRANSFERABLE_TO      {reason:"Log ingestion pipeline and query/visualization concepts transfer; Loki is simpler and label-indexed instead of full-text", weight:0.72}]->(loki)
MERGE (opentelemetry)-[:BRIDGES    {reason:"OpenTelemetry instruments application code and ships telemetry to Datadog's OTLP endpoint", weight:0.88}]->(datadog)

MERGE (vault)-[:OFTEN_USED_WITH    {reason:"Vault injects secrets into Kubernetes pods via the Vault Agent sidecar or CSI driver", weight:0.88}]->(kubernetes)
MERGE (vault)-[:OFTEN_USED_WITH    {reason:"Terraform uses Vault's provider to read secrets during infrastructure provisioning", weight:0.85}]->(terraform)
MERGE (consul)-[:OFTEN_USED_WITH   {reason:"Consul provides service discovery for HashiCorp-based microservice stacks alongside Vault and Terraform", weight:0.82}]->(vault)

MERGE (aws)-[:TRANSFERABLE_TO      {reason:"Cloud-native concepts (VPC, IAM, managed services) transfer across hyperscalers; service names differ", weight:0.72}]->(gcp)
MERGE (gcp)-[:TRANSFERABLE_TO      {reason:"Cloud-native concepts transfer; Azure integrates more tightly with Microsoft/enterprise tooling", weight:0.70}]->(azure)
MERGE (awslambda)-[:EQUIVALENT_IN  {reason:"All three are event-driven FaaS platforms; function handler, trigger and cold-start concepts transfer across the three", weight:0.95}]->(gcpfunctions)
MERGE (gcpfunctions)-[:EQUIVALENT_IN{reason:"Same FaaS model; skills transfer across cloud providers", weight:0.95}]->(azurefunctions)
MERGE (awslambda)-[:REQUIRES       {reason:"AWS Lambda is the AWS serverless runtime; basic AWS IAM and triggers knowledge is required", weight:0.90}]->(aws)
MERGE (gcpfunctions)-[:REQUIRES    {reason:"GCP Cloud Functions require GCP project and IAM setup", weight:0.90}]->(gcp)
MERGE (azurefunctions)-[:REQUIRES  {reason:"Azure Functions require an Azure subscription and Azure identity/RBAC", weight:0.90}]->(azure)
MERGE (vercel)-[:TRANSFERABLE_TO   {reason:"Both are frontend cloud platforms with automatic deployments, CDN and serverless functions; skills transfer", weight:0.88}]->(netlify)
MERGE (vercel)-[:OFTEN_USED_WITH   {reason:"Vercel is the primary deployment platform for Next.js applications", weight:0.92}]->(nextjs)

// ════════════════════════════════════════
// MESSAGING / STREAMING — TRANSFERABILITY
// ════════════════════════════════════════
MERGE (kafka)-[:TRANSFERABLE_TO    {reason:"Partitioned log, consumer group and offset management concepts partially transfer; Pulsar adds multi-tenancy and a different API", weight:0.75}]->(pulsar)
MERGE (rabbitmq)-[:TRANSFERABLE_TO {reason:"Queue, exchange and routing key concepts transfer; NATS is simpler and does not have persistent exchanges", weight:0.70}]->(nats)
MERGE (kinesis)-[:EQUIVALENT_IN    {reason:"Both are partitioned real-time event streaming platforms; Kafka is self-hosted, Kinesis is fully managed", weight:0.85}]->(kafka)
MERGE (pubsub)-[:EQUIVALENT_IN     {reason:"GCP Pub/Sub and Kafka both provide durable, ordered pub-sub messaging; Pub/Sub is fully managed", weight:0.80}]->(kafka)
MERGE (sqs)-[:EQUIVALENT_IN        {reason:"AWS SQS and RabbitMQ both provide reliable queue-based async message delivery", weight:0.82}]->(rabbitmq)
MERGE (eventbridge)-[:EXTENDS      {reason:"EventBridge is an AWS event bus that routes events from SQS, SNS and Lambda to targets", weight:0.90}]->(sqs)
MERGE (spark)-[:OFTEN_USED_WITH    {reason:"Kafka is commonly used as the input source for Spark Streaming micro-batch jobs", weight:0.88}]->(kafka)
MERGE (flink)-[:OFTEN_USED_WITH    {reason:"Kafka is the standard event source and sink for Flink streaming applications", weight:0.92}]->(kafka)

// ════════════════════════════════════════
// DATA ENGINEERING — TRANSFERABILITY
// ════════════════════════════════════════
MERGE (spark)-[:TRANSFERABLE_TO    {reason:"Distributed execution model and stateful operator concepts transfer; Flink is native streaming where Spark uses micro-batches", weight:0.75}]->(flink)
MERGE (flink)-[:TRANSFERABLE_TO    {reason:"Streaming pipeline and windowing concepts transfer back to Spark Structured Streaming", weight:0.73}]->(spark)
MERGE (airflow)-[:TRANSFERABLE_TO  {reason:"DAG concept, operator/task patterns and scheduler configuration transfer to Prefect; Prefect is more Pythonic", weight:0.82}]->(prefect)
MERGE (prefect)-[:TRANSFERABLE_TO  {reason:"Flow/task composition patterns transfer to Dagster; Dagster adds asset-centric materialization", weight:0.80}]->(dagster)
MERGE (delta_lake)-[:TRANSFERABLE_TO{reason:"Lakehouse ACID table concepts, schema evolution and time-travel queries transfer between Delta Lake and Iceberg", weight:0.88}]->(iceberg)
MERGE (iceberg)-[:TRANSFERABLE_TO  {reason:"Open table format metadata and snapshot management concepts transfer to Delta Lake", weight:0.85}]->(delta_lake)
MERGE (pandas)-[:TRANSFERABLE_TO   {reason:"DataFrame API, column operations and groupby patterns transfer; Polars uses a lazy/eager model instead of eager-only", weight:0.85}]->(polars)
MERGE (polars)-[:EVOLVED_INTO      {reason:"Polars is the high-performance modern replacement for Pandas; designed to supersede it for large-scale work", weight:0.85}]->(pandas)
MERGE (dask)-[:EXTENDS             {reason:"Dask wraps Pandas DataFrames and scales them across cores/nodes; all Pandas knowledge applies", weight:0.92}]->(pandas)
MERGE (numpy)-[:OFTEN_USED_WITH    {reason:"NumPy arrays are the backbone of Pandas DataFrames and most scientific Python libraries", weight:0.95}]->(pandas)
MERGE (numpy)-[:OFTEN_USED_WITH    {reason:"SciPy builds on top of NumPy for scientific and statistical computation", weight:0.95}]->(scipy)
MERGE (pandas)-[:OFTEN_USED_WITH   {reason:"Pandas is used for data preparation before training scikit-learn models", weight:0.88}]->(sklearn)

// ════════════════════════════════════════
// ML / AI — TRANSFERABILITY
// ════════════════════════════════════════
MERGE (tensorflow)-[:TRANSFERABLE_TO{reason:"Deep learning primitives (tensors, autograd, layers, optimisers) transfer; PyTorch uses a more Pythonic dynamic graph", weight:0.80}]->(pytorch)
MERGE (pytorch)-[:TRANSFERABLE_TO  {reason:"Tensor operations and neural network training loop patterns transfer; TensorFlow uses static graphs and a different API", weight:0.78}]->(tensorflow)
MERGE (jax)-[:TRANSFERABLE_TO      {reason:"NumPy-like tensor operations and autodiff concepts transfer; JAX compiles to XLA/TPU which PyTorch targets CUDA", weight:0.75}]->(pytorch)
MERGE (keras)-[:EXTENDS            {reason:"Keras is the high-level API bundled into TensorFlow 2.x; all Keras code runs on TensorFlow", weight:0.97}]->(tensorflow)
MERGE (keras)-[:TRANSFERABLE_TO    {reason:"Layer, model.fit and callback patterns transfer to PyTorch Lightning and other high-level wrappers", weight:0.72}]->(pytorch)
MERGE (sklearn)-[:OFTEN_USED_WITH  {reason:"Pandas provides the DataFrames that scikit-learn pipelines consume", weight:0.90}]->(pandas)
MERGE (sklearn)-[:OFTEN_USED_WITH  {reason:"NumPy arrays are scikit-learn's native data format", weight:0.92}]->(numpy)
MERGE (sklearn)-[:TRANSFERABLE_TO  {reason:"Pipeline, estimator and transformer API patterns transfer; XGBoost/LightGBM can be wrapped in sklearn Pipeline", weight:0.78}]->(xgboost)
MERGE (xgboost)-[:TRANSFERABLE_TO  {reason:"Gradient boosting hyperparameters and feature importance interpretation transfer almost 1:1", weight:0.92}]->(lightgbm)
MERGE (lightgbm)-[:TRANSFERABLE_TO {reason:"Tree-based boosting concepts transfer; CatBoost adds native categorical handling", weight:0.88}]->(catboost)
MERGE (huggingface)-[:OFTEN_USED_WITH{reason:"HuggingFace Transformers library requires PyTorch (or TF) as the tensor backend", weight:0.92}]->(pytorch)
MERGE (transformers)-[:PART_OF     {reason:"HF Transformers is the core library of the HuggingFace ecosystem", weight:1.0}]->(huggingface)
MERGE (diffusers)-[:PART_OF        {reason:"HF Diffusers is part of the HuggingFace ecosystem for generative image models", weight:1.0}]->(huggingface)
MERGE (transformers)-[:REQUIRES    {reason:"HF Transformers models require PyTorch or TensorFlow as the compute backend", weight:0.95}]->(pytorch)
MERGE (onnx)-[:BRIDGES             {reason:"ONNX lets models trained in PyTorch or TensorFlow be exported and run in any ONNX-compatible runtime", weight:0.95}]->(pytorch)
MERGE (onnx)-[:BRIDGES             {reason:"ONNX is the standard interchange format between TensorFlow and production inference runtimes", weight:0.92}]->(tensorflow)
MERGE (onnx)-[:BRIDGES             {reason:"ONNX models are loaded directly into Triton Inference Server for GPU-accelerated serving", weight:0.95}]->(triton)
MERGE (vllm)-[:TRANSFERABLE_TO     {reason:"High-throughput LLM inference server configuration and batching concepts transfer between vLLM and TGI", weight:0.88}]->(tgi)
MERGE (llama_cpp)-[:TRANSFERABLE_TO{reason:"Quantised model loading and context management concepts transfer to vLLM; llama.cpp targets CPU, vLLM targets GPU", weight:0.72}]->(vllm)
MERGE (spacy)-[:TRANSFERABLE_TO    {reason:"NLP pipeline (tokeniser, NER, parser) concepts transfer; spaCy is production-grade, NLTK is educational", weight:0.78}]->(nltk)

// ════════════════════════════════════════
// MLOPS — TRANSFERABILITY
// ════════════════════════════════════════
MERGE (mlflow)-[:TRANSFERABLE_TO   {reason:"Experiment run logging, metric tracking and model registry concepts transfer; W&B has a richer UI and real-time viz", weight:0.82}]->(wandb)
MERGE (wandb)-[:TRANSFERABLE_TO    {reason:"Experiment tracking and artifact versioning concepts transfer to Neptune; similar API surface", weight:0.85}]->(neptune)
MERGE (sagemaker)-[:EQUIVALENT_IN  {reason:"All three are cloud-managed ML platforms; training job, endpoint and experiment tracking concepts transfer across them", weight:0.92}]->(vertexai)
MERGE (vertexai)-[:EQUIVALENT_IN   {reason:"Managed ML pipeline and model registry concepts transfer across the three cloud ML platforms", weight:0.92}]->(azureml)
MERGE (seldon)-[:TRANSFERABLE_TO   {reason:"Kubernetes-native model serving InferenceService CRD patterns transfer between Seldon and KServe", weight:0.88}]->(kserve)
MERGE (bentoml)-[:TRANSFERABLE_TO  {reason:"Model packaging, service definition and deployment pipeline concepts transfer; TorchServe is PyTorch-specific", weight:0.78}]->(torchserve)
MERGE (torchserve)-[:REQUIRES      {reason:"TorchServe is PyTorch's native serving runtime; PyTorch model knowledge is required", weight:0.95}]->(pytorch)
MERGE (kubeflow)-[:REQUIRES        {reason:"Kubeflow is a Kubernetes-native ML platform; K8s knowledge is required", weight:0.95}]->(kubernetes)
MERGE (feast)-[:TRANSFERABLE_TO    {reason:"Feature store concepts (online/offline stores, feature views, entity keys) transfer between Feast and Tecton", weight:0.88}]->(tecton)
MERGE (ray)-[:BRIDGES              {reason:"Ray bridges distributed ML training (Ray Train) and online serving (Ray Serve) in a single unified framework", weight:0.90}]->(mlflow)
MERGE (dvc)-[:OFTEN_USED_WITH      {reason:"DVC tracks data and model versions while MLflow tracks experiments; the two are complementary", weight:0.88}]->(mlflow)
MERGE (great_exp)-[:TRANSFERABLE_TO{reason:"Data expectation and validation suite concepts transfer; Evidently adds drift detection on top", weight:0.80}]->(evidently)
MERGE (mlflow)-[:BRIDGES           {reason:"MLflow experiment tracking integrates with SageMaker for model registry and deployment", weight:0.85}]->(sagemaker)
MERGE (triton)-[:REQUIRES          {reason:"Triton Inference Server is primarily used with NVIDIA GPUs; CUDA and GPU knowledge are beneficial", weight:0.85}]->(onnx)

// ════════════════════════════════════════
// LLM — TRANSFERABILITY
// ════════════════════════════════════════
MERGE (langchain)-[:TRANSFERABLE_TO{reason:"Chain, retriever and document loader abstractions transfer; LlamaIndex is more specialised for indexing and RAG", weight:0.78}]->(llamaindex)
MERGE (llamaindex)-[:TRANSFERABLE_TO{reason:"RAG pipeline and query engine concepts transfer back to LangChain retrievers", weight:0.75}]->(langchain)
MERGE (langgraph)-[:EXTENDS        {reason:"LangGraph adds stateful graph execution to LangChain; LangChain knowledge is required", weight:0.97}]->(langchain)
MERGE (langchain)-[:REQUIRES       {reason:"LangChain needs an LLM provider (OpenAI, Anthropic, HuggingFace) to function", weight:0.95}]->(openai)
MERGE (llamaindex)-[:REQUIRES      {reason:"LlamaIndex needs an LLM provider and an embedding model to build indexes", weight:0.90}]->(openai)
MERGE (autogen)-[:TRANSFERABLE_TO  {reason:"Multi-agent orchestration, tool calling and conversation loop patterns transfer between AutoGen and CrewAI", weight:0.85}]->(crewai)
MERGE (semantic_kernel)-[:EQUIVALENT_IN{reason:"Semantic Kernel (.NET/enterprise) and LangChain (Python) are equivalent LLM orchestration frameworks for their respective ecosystems", weight:0.85}]->(langchain)
MERGE (litellm)-[:BRIDGES          {reason:"LiteLLM provides a single unified API that wraps OpenAI, Anthropic, Gemini and other providers", weight:0.97}]->(openai)
MERGE (litellm)-[:BRIDGES          {reason:"LiteLLM wraps Anthropic's API under the OpenAI-compatible interface", weight:0.97}]->(anthropic_api)
MERGE (litellm)-[:BRIDGES          {reason:"LiteLLM wraps Gemini under the OpenAI-compatible interface", weight:0.95}]->(gemini)
MERGE (openai)-[:TRANSFERABLE_TO   {reason:"Prompt engineering, function-calling/tool-use and streaming response patterns transfer across all major LLM providers", weight:0.85}]->(anthropic_api)
MERGE (anthropic_api)-[:TRANSFERABLE_TO{reason:"LLM API concepts (system prompt, turn-based conversation, streaming) transfer to OpenAI and Gemini", weight:0.85}]->(openai)
MERGE (mistral)-[:TRANSFERABLE_TO  {reason:"Open-weight LLM fine-tuning, GGUF quantisation and local inference skills transfer between Mistral and LLaMA families", weight:0.88}]->(llama)
MERGE (langchain)-[:OFTEN_USED_WITH{reason:"LangChain integrates with HuggingFace Hub for open-source model access", weight:0.85}]->(huggingface)
MERGE (dspy)-[:TRANSFERABLE_TO     {reason:"Treating LLM calls as optimisable programs rather than static prompts is a shared philosophy; DSPy is more formal", weight:0.72}]->(langchain)
MERGE (promptflow)-[:EQUIVALENT_IN {reason:"Prompt Flow (Azure) is the Microsoft LLMOps equivalent to MLflow for tracking and deploying LLM pipelines", weight:0.85}]->(mlflow)
MERGE (guardrails)-[:OFTEN_USED_WITH{reason:"Guardrails AI is used to validate and fix LLM outputs in LangChain pipelines", weight:0.88}]->(langchain)
MERGE (guardrails)-[:OFTEN_USED_WITH{reason:"Guardrails validates outputs coming from OpenAI API calls", weight:0.85}]->(openai)
MERGE (llamaindex)-[:OFTEN_USED_WITH{reason:"LlamaIndex commonly uses Pinecone as its vector store for RAG", weight:0.88}]->(pinecone)

// ════════════════════════════════════════
// SECURITY — TRANSFERABILITY
// ════════════════════════════════════════
MERGE (burpsuite)-[:TRANSFERABLE_TO{reason:"HTTP interception proxy, scanner and active/passive testing methodology transfer; OWASP ZAP is the open-source equivalent", weight:0.85}]->(owasp)
MERGE (owasp)-[:TRANSFERABLE_TO    {reason:"DAST scanning rules and vulnerability reporting skills transfer back to Burp Suite professional features", weight:0.80}]->(burpsuite)
MERGE (splunk)-[:TRANSFERABLE_TO   {reason:"SIEM log ingestion, correlation rule and alert concepts transfer; Wazuh is open-source and agent-based", weight:0.82}]->(ossec)
MERGE (snort)-[:TRANSFERABLE_TO    {reason:"Network IDS rule writing and signature-based detection concepts transfer; both tools share rule syntax concepts", weight:0.88}]->(ossec)
MERGE (trivy)-[:OFTEN_USED_WITH    {reason:"Trivy scans Docker images as part of the container build pipeline", weight:0.92}]->(docker)
MERGE (trivy)-[:OFTEN_USED_WITH    {reason:"Trivy is integrated into Kubernetes admission controllers and GitOps pipelines", weight:0.85}]->(kubernetes)
MERGE (falco)-[:OFTEN_USED_WITH    {reason:"Falco monitors syscall events from containers running in Kubernetes", weight:0.92}]->(kubernetes)
MERGE (opa)-[:OFTEN_USED_WITH      {reason:"OPA is used as the Kubernetes admission controller (Gatekeeper) for policy enforcement", weight:0.92}]->(kubernetes)
MERGE (sonarqube)-[:OFTEN_USED_WITH{reason:"SonarQube is integrated as a step inside GitHub Actions CI pipelines for SAST", weight:0.88}]->(githubactions)
MERGE (keycloak)-[:IMPLEMENTS      {reason:"Keycloak is a full OAuth2/OIDC identity provider implementation", weight:1.0}]->(oauth2)
MERGE (oauth2)-[:OFTEN_USED_WITH   {reason:"JWT is the standard token format used in OAuth 2.0 and OIDC access tokens", weight:0.95}]->(jwt)
MERGE (vault)-[:OFTEN_USED_WITH    {reason:"Terraform reads secrets from Vault to avoid hardcoded credentials in IaC code", weight:0.88}]->(terraform)

// ════════════════════════════════════════
// MOBILE — TRANSFERABILITY
// ════════════════════════════════════════
MERGE (reactnative)-[:TRANSFERABLE_TO{reason:"React component model, hooks and JSX transfer directly; React Native replaces the DOM with native UI primitives", weight:0.88}]->(flutter)
MERGE (reactnative)-[:REQUIRES     {reason:"React Native uses React's component model; React knowledge is required", weight:0.95}]->(react)
MERGE (expo)-[:EXTENDS             {reason:"Expo is a managed React Native platform; all React Native knowledge applies plus Expo SDK APIs", weight:0.97}]->(reactnative)
MERGE (ionic)-[:TRANSFERABLE_TO    {reason:"Web-based cross-platform mobile development concepts transfer; Capacitor is the Ionic-native runtime bridge", weight:0.82}]->(reactnative)
MERGE (capacitor)-[:EXTENDS        {reason:"Capacitor is the native runtime layer that Ionic apps run on; Ionic knowledge is required to use Capacitor effectively", weight:0.97}]->(ionic)
MERGE (ionic)-[:REQUIRES           {reason:"Ionic uses web technologies (Angular/React/Vue) inside Capacitor; a web framework is required", weight:0.90}]->(angular)
MERGE (kotlin_android)-[:EQUIVALENT_IN{reason:"Swift (iOS native) and Kotlin (Android native) are the platform-native language pair for mobile development", weight:0.88}]->(swift)
MERGE (kotlin_android)-[:REQUIRES  {reason:"Kotlin Android development runs on the JVM/Android runtime; Java/Kotlin JVM knowledge is required", weight:0.90}]->(kotlin)

// ════════════════════════════════════════
// CROSS-DOMAIN BRIDGES
// ════════════════════════════════════════
MERGE (python)-[:BRIDGES           {reason:"Python is the primary language that unifies Backend, Data Engineering, ML and LLM domains", weight:1.0}]->(tensorflow)
MERGE (python)-[:BRIDGES           {reason:"Python knowledge is the entry point to the entire ML/data science ecosystem", weight:1.0}]->(sklearn)
MERGE (python)-[:BRIDGES           {reason:"Python knowledge is required for all major LLM orchestration frameworks", weight:1.0}]->(langchain)
MERGE (python)-[:OFTEN_USED_WITH   {reason:"FastAPI is the standard Python framework for serving ML models as REST APIs", weight:0.92}]->(fastapi)
MERGE (python)-[:OFTEN_USED_WITH   {reason:"Airflow DAGs are written in Python; Python is the orchestration language", weight:0.95}]->(airflow)
MERGE (python)-[:OFTEN_USED_WITH   {reason:"PySpark is the Python API for Apache Spark; Python skills transfer directly", weight:0.90}]->(spark)
MERGE (kafka)-[:BRIDGES            {reason:"Kafka bridges real-time backend event streaming into ML feature store ingestion pipelines", weight:0.88}]->(feast)
MERGE (kubernetes)-[:BRIDGES       {reason:"Kubernetes bridges DevOps and MLOps by serving as the runtime for Kubeflow ML pipelines", weight:0.90}]->(kubeflow)
MERGE (graphql)-[:BRIDGES          {reason:"GraphQL bridges the Frontend's data-fetching needs and the Backend's schema-driven API design", weight:0.90}]->(graphqlserver)
MERGE (opentelemetry)-[:BRIDGES    {reason:"OpenTelemetry bridges application instrumentation and observability backends across all languages", weight:0.92}]->(datadog)
MERGE (wasm)-[:BRIDGES             {reason:"WebAssembly bridges high-performance systems code (Rust/C++) with browser execution environments", weight:0.88}]->(rust)
MERGE (nodejs)-[:BRIDGES           {reason:"Node.js bridges JavaScript frontend skills to server-side backend development", weight:0.95}]->(javascript)
MERGE (dbt)-[:BRIDGES              {reason:"dbt bridges software engineering best practices (version control, tests, CI) with SQL-based data transformations", weight:0.90}]->(snowflake)
MERGE (mlflow)-[:BRIDGES           {reason:"MLflow bridges offline ML experimentation and production model deployment on SageMaker", weight:0.88}]->(sagemaker)
MERGE (onnx)-[:BRIDGES             {reason:"ONNX bridges ML training frameworks (PyTorch, TF) with production inference servers (Triton, ONNX Runtime)", weight:0.95}]->(triton)

// =============================================================================
// USEFUL MATCHING QUERIES
// =============================================================================
//
// 1. All technologies whose skills transfer to "React":
//    MATCH (a:Technology)-[r:TRANSFERABLE_TO]->(b:Technology {name:"React"})
//    RETURN a.name, r.weight ORDER BY r.weight DESC
//
// 2. Expand a candidate skill set 2 hops via transferability + necessity:
//    MATCH (t:Technology) WHERE t.name IN $profile_skills
//    MATCH (t)-[:TRANSFERABLE_TO|EQUIVALENT_IN|EXTENDS|REQUIRES*1..2]-(related)
//    RETURN DISTINCT related.name, related.category
//
// 3. Full transferability neighbourhood of "Kubernetes" (depth 2):
//    MATCH path = (t:Technology {name:"Kubernetes"})-[:TRANSFERABLE_TO|REQUIRES|OFTEN_USED_WITH*1..2]-(n)
//    RETURN path
//
// 4. Match a profile to a job with weighted score:
//    MATCH (pt:Technology) WHERE pt.name IN $profile_skills
//    OPTIONAL MATCH (pt)-[r:TRANSFERABLE_TO|EQUIVALENT_IN]->(related)
//    WITH collect(DISTINCT pt.name) + collect(DISTINCT related.name) AS expanded
//    MATCH (jt:Technology) WHERE jt.name IN $job_skills
//    RETURN size([s IN expanded WHERE s IN $job_skills]) * 1.0 / size($job_skills) AS match_score
//
// 5. Find all technologies by category for UI filtering:
//    MATCH (t:Technology) RETURN t.category, collect(t.name) ORDER BY t.category
//
// =============================================================================
