# Systems Architecture — Operational Doctrine

Distilled from 12 master-level resources on distributed systems, data architecture, security, and organizational design.

## Reliability and Fault Tolerance

- **Failure is a constant, not an edge case.** Design systems assuming hardware fails (drops packets, corrupts data, dies without warning), software has bugs (drops messages, corrupts internal state), and operators make mistakes (drops messages, corrupts internal state). Every component must be assumed to fail at any time (DDIA). Build fault-tolerance into the architecture, not as an afterthought: detect failures (heartbeat checks, health endpoints), fail fast (don't retry a dead node 100 times), and recover (replication, backups, circuit breakers).
- **CAP theorem is a constraint, not a choice.** You pick 2 of 3 (consistency, availability, partition tolerance). In a network partition (which WILL happen), you must choose between consistency (reject writes) and availability (serve stale data). Design around the trade-off explicitly: document what your system sacrifices and why. The choice is not permanent — a system might be CP for payments but AP for a product catalog.
- **Replication lag is a bug waiting to happen.** Single-leader replication (one writable node, multiple read copies) creates a gap between when a write is committed and when readers see it. Design around this: use read-after-write consistency (redirect a reader to the writing node after a write), monotonic reads (pin a reader to a replica once chosen), or consistent prefix reads (guarantee that a reader never sees a later write without the earlier one). Never assume a replica is "current."

## Scalability and Performance

- **Scale horizontally before vertically.** Vertical scaling (bigger machines) hits a ceiling (hardware limits, cost curves). Horizontal scaling (more machines) is bounded only by your ability to distribute work (sharding, load balancing, caching). Design systems to add capacity by adding machines, not by upgrading a single machine.
- **Latency outliers destroy user experience.** The 99th-percentile response time matters more than the average (DDIA). A system that responds in 10ms 99% of the time and 10s 1% of the time is worse than a system that responds in 100ms 100% of the time. Design for outliers: set timeouts (don't wait forever on a slow node), use circuit breakers (stop sending requests to a failing node), and add caches (avoid expensive operations).
- **Caching is a trade-off, not a free optimization.** Cache-aside (load on miss, store on read), write-through (update cache and backend simultaneously), write-behind (update cache, async flush to backend), and refresh-ahead (pre-load before expiry) each have different consistency/cost profiles (system-design-primer). Choose the cache strategy that matches your consistency requirements: a product catalog (stale data OK → cache-aside or refresh-ahead) vs a bank balance (stale data unacceptable → write-through or no cache).

## Data Architecture

- **The data model defines the system's shape.** Relational (SQL) databases enforce structure (schema, foreign keys) but resist schema changes. Document databases (MongoDB) are flexible (no schema) but lose referential integrity. Graph databases (Neo4j) excel at relationship-heavy queries (social networks, recommendation engines) but struggle with aggregations (DDIA). Choose the data model that matches the access patterns, not the other way around.
- **B-Trees vs LSM-trees: a write-heavy vs read-heavy trade-off.** B-Trees (used by PostgreSQL, MySQL) are optimized for random reads (point queries, range queries) but suffer on heavy writes (need to move data around on disk). LSM-trees (used by Cassandra, RocksDB) buffer writes in memory (memtable) and flush to disk as sorted runs (merging periodically) — fast writes, slower reads (may need to merge multiple runs). Design the storage engine around the workload: a logging system (write-heavy → LSM) vs a search engine (read-heavy → B-Tree).
- **Strong consistency (ACID) vs eventual consistency (BASE).** ACID (Atomicity, Consistency, Isolation, Durability) guarantees a transaction either completes fully or not at all (financial payments, inventory management). BASE (Basically Available, Soft state, Eventual consistency) accepts that a system might be temporarily inconsistent (social media feeds, analytics) but will converge eventually (DDIA). Design around the semantics: payments need ACID (serializable isolation); a product catalog might need BASE (stale data is acceptable).

## Distributed Systems Patterns

- **Microservices create coupling, not eliminate it.** Moving from a monolith to microservices doesn't eliminate coupling — it moves it from internal function calls (cheap, synchronous) to network calls (expensive, asynchronous, unreliable) (DDIA). Design microservices around bounded contexts (DDD): a service owns a specific domain (order management, user profiles) and communicates through a well-defined API (REST, gRPC). Before splitting a monolith into microservices, understand the coupling (data dependencies, transactional requirements) — splitting the wrong way creates a distributed monolith (harder to debug, slower).
- **Message queues decouple producers from consumers.** A message queue (RabbitMQ, Kafka) allows a producer (order service) to send a message (order created) without waiting for the consumer (shipping service) to be ready (DDIA). Design around the trade-offs: a queue adds latency (message sits in queue) but increases reliability (message persists even if consumer is down). Choose a queue that matches the semantics: a fire-and-forget queue (notifications) vs a durable queue (financial payments).
- **The 12-factor app is a checklist, not a theory.** 12 principles for building SaaS apps (codebase, dependencies, config, backing services, build/release/run, processes, port binding, concurrency, disposability, dev/prod parity, logs, admin processes) (12factor.net). Design apps that follow these factors: store config in the environment (not the codebase), treat backing services as attached resources (swap a database without changing the app), maximize robustness with disposable processes (restart a crashed container without manual intervention).

## Organizational Design

- **Team topology defines system architecture.** The structure of teams (stream-aligned, platform, enabling, complicated-subsystem) determines the structure of the system (Team Topologies). Design teams around value streams (order fulfillment, user onboarding) not around technology (database team, API team). A platform team (provides internal tooling) might create a platform (Kubernetes, internal API gateway) that stream-aligned teams consume (collaboration mode). Keep teams small (cognitive limits: ~5-15 people) and connected to customers (Team Topologies).
- **Cognitive load is a system constraint.** Every team has a finite capacity (Team Topologies). Design systems so that a team owns a bounded context (order management) without needing to understand the internals of another (payment processing). Interaction modes (collaboration, X-as-a-Service, facilitation) determine how teams work together: a platform team (X-as-a-Service) might provide a search API that a stream-aligned team (product catalog) consumes without understanding the search internals (Team Topologies).

## Security

- **Security is a systems problem, not a cryptography problem.** Ross Anderson's Security Engineering shows that the hardest security problems are not mathematical (break the encryption) but human (phishing, coercion, social engineering) (Security Engineering). Design security around the threat model: a nuclear command-and-control system (high security, air-gapped) vs a consumer app (low security, user-friendly). Assume the network is hostile (encrypt in transit, encrypt at rest). Design for the worst-case (data breach, insider threat, supply-chain attack).
- **Side channels leak information.** Even a correctly-implemented encryption algorithm leaks information through timing (how long a comparison took), power consumption (how much power a CPU used), or electromagnetic emissions (Security Engineering). Design security around side channels: constant-time comparisons (don't short-circuit a string comparison), random delays (mask timing information), and physical security (prevent power analysis attacks).

## Source Code and Language Design

- **An interpreter is a program that runs another program.** SICP shows that writing an interpreter (a program that executes a language) teaches the deepest concepts: evaluation (how expressions are reduced to values), environment (how variables are bound to values), and continuation (what happens after a value is computed) (SICP). Design a language (or a DSL) by writing an interpreter: the interpreter IS the language specification (no ambiguity, no hand-waving).
- **A compiler pipeline (scan → parse → semantic analysis → optimization → code generation) is a metaphor for thinking.** Compilers (Thain) break a problem into stages (lexical analysis, syntax analysis, semantic analysis, optimization, code generation). Design a thinking process the same way: break a problem into stages (understand the input, validate the structure, analyze the semantics, optimize the result, generate the output). Each stage has a contract (input → output) — a bug in one stage might not manifest until a later stage (debug the earliest possible stage).

## Software Design Principles

- **SOLID principles are a checklist for maintainable code.** Single Responsibility (one reason to change), Open/Closed (open for extension, closed for modification), Liskov Substitution (subtypes must be substitutable), Interface Segregation (many small interfaces > one fat interface), Dependency Inversion (depend on abstractions, not concretions) (Codely PRO). Design code that follows these principles: a class (order processor) that does too much (processes payments, sends emails, updates inventory) violates SRP (Single Responsibility Principle) — split into smaller classes (payment processor, notification service, inventory manager).
- **Hexagonal (ports-and-adapters) architecture decouples the core from the outside.** The core (domain logic) sits in the center (no dependencies on frameworks, databases, or UI). External systems (databases, web frameworks, UI) sit in the outer rings (adapters) that implement the core's ports (interfaces). Design the core (order processing) without dependencies (no database imports, no framework imports) — the core only defines interfaces (ports) that the outer rings (adapters) implement (Codely PRO).

## Algorithms and Complexity

- **Algorithmic analysis (Big-O) is a contract, not a suggestion.** Sedgewick's Algorithms shows that a sorting algorithm (mergesort: guaranteed n log n) might be slower than a simpler algorithm (insertion sort: n²) on small inputs (constant factors matter). Design around the input size: a hash table (O(1) average) might be slower than a linear search (O(n)) on 10 elements (hash function overhead). Know the input size distribution (small, medium, large) and pick the algorithm that matches (Sedgewick).
- **Reducible problems share solutions.** If a problem (traveling salesman) can be reduced to another (graph optimization), a solution to the second (approximation algorithm) might be a good starting point for the first (Sedgewick). Design around reductions: a problem (search a sorted array) might be reducible to a known algorithm (binary search). Before writing a custom algorithm, check if the problem reduces to a known one (sorting, graph search, dynamic programming).

## Sources covered this batch
- #master1 [oreilly.com] — DDIA (Kleppmann)
- #master2 [github.com/donnemartin/system-design-primer] — system-design-primer (donnemartin)
- #master3 [microsoft.com] — Designing Distributed Systems (Burns)
- #master6 [domainlanguage.com] — DDD (Evans)
- #master7 [ocw.mit.edu] — SICP (Abelson/Sussman)
- #master8 [stanford.edu ~knuth] — TAOCP (Knuth)
- #master9 [compilerbook.org] — Compilers (Thain)
- #master10 [algs4.cs.princeton.edu] — Algorithms (Sedgewick & Wayne)
- #master11 [codely.io] — Codely PRO (SOLID, DDD, Hexagonal)
- #master13 [cam.ac.uk ~rwa2] — Security Engineering (Anderson)
- #master15 [12factor.net] — 12-Factor App (Wiggins)
- #master16 [teamtopologies.com] — Team Topologies (Skelton & Pais)
