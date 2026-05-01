# 💣 Bombardment Engine — AI-Powered Mutation Fuzzing Suite

<div align="center">

**A high-performance, mutation-based fuzz testing engine with real-time telemetry and AI-powered strategy selection via Gemini 2.5 Flash.**

![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi&logoColor=white)
![WebSocket](https://img.shields.io/badge/WebSocket-Real--time-FF6F00?style=flat-square)
![Gemini AI](https://img.shields.io/badge/Gemini_2.5-Flash_AI-4285F4?style=flat-square&logo=google&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

</div>

---

## 📖 Overview

The **Bombardment Engine** is a full-stack fuzzing framework that automates vulnerability discovery through intelligent input mutation. It is grounded in the formal taxonomy established by Manès et al. in *"The Art, Science, and Engineering of Fuzzing: A Survey"* (arXiv:1812.00140).

### Key Differentiator: AI Pre-Analysis

Before bombardment begins, the engine sends the target system's source code, binary metadata, and sample inputs to **Google Gemini 2.5 Flash**, which analyzes the target's input structure and selects only the most effective mutation algorithms — eliminating wasted cycles on irrelevant strategies.

```
User clicks 🧠 Analyze
    ↓
POST /api/analyze → strategy_analyzer.py
    ↓
Target description + source + seeds → Gemini 2.5 Flash API
    ↓
Gemini responds: "Arithmetic Mutation, Block-Based Mutation"
    ↓
Parsed → only those algorithms are activated
    ↓
User clicks ▶ Start → bombardment with optimized strategy
```

---
# The Fuzzing Bombardment Engine: A-Z Architecture & Implementation

This document provides a comprehensive blueprint for building the "Bombardment" (Input Generation) phase of the fuzz testing engine, heavily grounded in the formal specifications established by Manès et al. in *The Art, Science, and Engineering of Fuzzing: A Survey* [cite: 1812.00140v4 (1).pdf].

## Phase 1: The Core Philosophy & Theory

### 1.1 Why Pure Randomness Fails
When attempting to break a system, the initial instinct is often to write a script that throws completely random byte streams at the target. The research paper explicitly identifies this as highly inefficient [cite: 1812.00140v4 (1).pdf]. 
* **The Mathematics:** If a target program contains a simple conditional statement like `if (input == 42)`, the probability of a purely random fuzzer guessing the correct 32-bit integer is a dismal $1/2^{32}$ [cite: 1812.00140v4 (1).pdf].
* **The Parser Wall:** Programs expecting structured inputs (like JSON, MP3, or specific protocol packets) will reject completely random data at the initial parsing stage. The data will never reach the deeper, complex functions where critical vulnerabilities (like buffer overflows or race conditions) typically hide [cite: 1812.00140v4 (1).pdf].

### 1.2 The Seed-Based Strategy
To bypass the "parser wall," the engine must employ a "model-less (mutation-based)" approach [cite: 1812.00140v4 (1).pdf]. 
1. **The Seed:** We start with a highly structured, perfectly valid input of the type the target program expects (e.g., a valid configuration file) [cite: 1812.00140v4 (1).pdf].
2. **The Protrusion:** The engine then mutates only a tiny fraction of this valid seed. This generates a test case that is syntactically valid enough to pass initial checks but contains abnormal semantic values designed to trigger fatal crashes [cite: 1812.00140v4 (1).pdf].

---

## Phase 2: System Architecture

Running natively on a Fedora Linux environment provides a massive advantage for this architecture, specifically when tracking the execution of low-level compiled binaries. 

### 2.1 The Python Orchestrator
Python acts as the central orchestrator and mutation scheduler. It is responsible for:
* Loading the initial seed file into memory.
* Applying the four core mutation algorithms at high speed.
* Utilizing libraries like `subprocess` to spawn the vulnerable C++ target binary.
* Piping the mutated payload directly into the binary's standard input.
* Monitoring the OS-level signals for crashes (e.g., `SIGSEGV` for segmentation faults).

---

## Phase 3: The 4 Core Mutation Algorithms

The python engine must continuously cycle the seed through four distinct mutation algorithms to maximize the stress on the target system.

### Algorithm 1: Bit-Flipping
This is a foundational technique where the fuzzer alters a predetermined or random number of bits within the seed [cite: 1812.00140v4 (1).pdf]. 
* **Implementation:** The engine should define a configurable `mutation_ratio`, dictating how many bit positions to flip per fuzzing iteration [cite: 1812.00140v4 (1).pdf]. 
* **Optimization:** Advanced fuzzing frameworks dynamically adjust this ratio, allocating more CPU cycles to mutation ratios that statistically yield deeper code coverage [cite: 1812.00140v4 (1).pdf].

### Algorithm 2: Arithmetic Mutation
Instead of flipping bits blindly, this algorithm manipulates the data mathematically.
* **Implementation:** The engine isolates a specific byte sequence (like 4 bytes), treats it as an integer ($i$), and replaces it with $i \pm r$ [cite: 1812.00140v4 (1).pdf].
* **The Bounding Rule:** The value $r$ is a randomly generated small integer. For example, replacing a sequence with $i \pm r$ where $0 \le r < 35$ bounds the mutation to a small variance [cite: 1812.00140v4 (1).pdf]. This is specifically designed to hunt for "off-by-one" memory errors and integer underflows.

### Algorithm 3: Block-Based Mutation
This technique treats the seed file not as individual bits, but as larger chunks or "blocks" of data [cite: 1812.00140v4 (1).pdf].
* **Implementation:** The Python engine should randomly slice the byte array and perform structural operations:
    * **Insert:** Place a randomly generated block into the middle of the seed [cite: 1812.00140v4 (1).pdf].
    * **Delete:** completely remove a selected block, shrinking the file size [cite: 1812.00140v4 (1).pdf].
    * **Permute:** Scramble the order of a sequence of blocks [cite: 1812.00140v4 (1).pdf].
    * **Cross-pollinate:** Take a block from one seed and splice it into a completely different seed [cite: 1812.00140v4 (1).pdf].

### Algorithm 4: Dictionary-Based (Semantic) Mutation
This algorithm injects predefined values known to cause issues across almost all software systems.
* **Implementation:** The engine maintains a dictionary of values with heavy "semantic weight" [cite: 1812.00140v4 (1).pdf]. 
* **Payload Examples:** * Integers: `0`, `1`, `-1`, `MAX_INT`, `MIN_INT` [cite: 1812.00140v4 (1).pdf].
    * Format Strings: `%s`, `%n`, `%x` (designed to exploit C/C++ `printf` vulnerabilities) [cite: 1812.00140v4 (1).pdf].
    * The engine searches the seed for strings or integers and replaces them entirely with these dictionary payloads.

---

## Phase 4: The Execution Pipeline

To create an enterprise-grade threat detection loop, the bombardment must be continuous and highly tracked.

1. **Initialize `seed_pool`:** Load valid inputs.
2. **Schedule:** Select a seed from the pool.
3. **Mutate:** Pass the seed through Algorithms 1-4, generating `mutated_payload`.
4. **Execute:** Spawn the C++ target, feeding it `mutated_payload`.
5. **Monitor:** If `return_code == -11` (Segmentation Fault), trigger the crash handler.
6. **Log (Triage):** Save `mutated_payload` directly to the `crash_logs` directory to capture the exact input-to-failure chain.
7. **Broadcast:** Push the crash event and the payload hash via WebSockets to the frontend dashboard.


## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                  FRONTEND (Vanilla JS)              │
│  ┌──────────┐ ┌──────────┐ ┌───────────────────┐   │
│  │ Analysis │ │ Stats    │ │ Live Crash Feed   │   │
│  │ Panel    │ │ Cards    │ │ + Activity Console│   │
│  └──────────┘ └──────────┘ └───────────────────┘   │
└──────────────────────┬──────────────────────────────┘
                       │ WebSocket (bidirectional)
┌──────────────────────▼──────────────────────────────┐
│               FastAPI SERVER (server.py)            │
│  /api/analyze  /api/start  /api/stop  /ws           │
└──────┬────────────────┬─────────────────────────────┘
       │                │
┌──────▼──────┐  ┌──────▼──────────────────────────┐
│  Gemini 2.5 │  │     ENGINE (orchestrator.py)     │
│  Flash API  │  │  ┌────────────────────────────┐  │
│  (Strategy) │  │  │   Structure-Aware Mutator  │  │
│             │  │  │  ┌─────────┐ ┌──────────┐  │  │
└─────────────┘  │  │  │Bit Flip │ │Arithmetic│  │  │
                 │  │  ├─────────┤ ├──────────┤  │  │
                 │  │  │ Block   │ │Dictionary│  │  │
                 │  │  └─────────┘ └──────────┘  │  │
                 │  └────────────────────────────┘  │
                 │  ┌──────────┐  ┌──────────────┐  │
                 │  │ SeedPool │  │ CrashHandler │  │
                 │  └──────────┘  └──────────────┘  │
                 └──────────────┬───────────────────┘
                                │ subprocess (stdin pipe)
                 ┌──────────────▼───────────────────┐
                 │    TARGET BINARY (vulnerable.cpp) │
                 │  Buffer overflow │ Format string  │
                 │  Integer overflow│ OOB read       │
                 └──────────────────────────────────┘
```

---

## ⚡ Mutation Algorithms

| Algorithm | Strategy | What It Does |
|-----------|----------|-------------|
| **Bit Flip** | Stochastic | Flips 25% of bits in the value bytes, corrupting data structures |
| **Arithmetic** | Boundary | Applies `i ± r` perturbations (±350 range) to trigger integer overflow/underflow |
| **Block-Based** | Structural | Insert, delete, permute, or cross-pollinate blocks of bytes |
| **Dictionary** | Semantic | Injects format strings (`%s%n`), boundary integers (`0x7FFFFFFF`), overflow payloads (`A*1024`) |

### Structure-Aware Design

The engine **parses `key=value` lines** and mutates **only the value portion**, preserving the key structure. This ensures the target binary's parser always routes mutated payloads to the vulnerable functions (`strcpy`, `printf`, `atoi`, etc.).

```
Input:   name=FuzzTest        →  name=AAAA...(128 bytes)   ← value mutated
         format=Hello World   →  format=%s%s%s%n%n         ← value mutated
         count=10             →  count=2147483647           ← value mutated
         ↑ keys never touched
```

---

## 🎯 Vulnerable Target

The included C++ binary (`target/vulnerable.cpp`) contains **4 intentional vulnerabilities**:

| Vulnerability | Function | Trigger |
|---------------|----------|---------|
| **Stack Buffer Overflow** | `strcpy` into 64-byte buffer | `name` value > 64 chars |
| **Format String Exploit** | `printf(user_input)` | `format` contains `%s`, `%n`, `%x` |
| **Integer Overflow** | `count * sizeof(int)` → `malloc` | `count` near `INT_MAX` |
| **Out-of-Bounds Read** | `data_buffer[index]` | `index` ≥ 16 |

Compiled with: `clang++ -o target/vulnerable -fno-stack-protector -O0 target/vulnerable.cpp`

---

## 📁 Project Structure

```
fuzz-bombardment-engine/
├── server.py                    # FastAPI server (REST + WebSocket)
├── .env                         # Gemini API key
├── requirements.txt             # Python dependencies
│
├── engine/
│   ├── orchestrator.py          # Core fuzzing loop + structure-aware mutation
│   ├── strategy_analyzer.py     # Gemini 2.5 Flash integration
│   ├── seed_pool.py             # Seed file manager with crash weighting
│   ├── crash_handler.py         # Signal triage + crash log persistence
│   └── mutators/
│       ├── __init__.py
│       ├── bit_flipper.py       # Bit-flip mutation algorithm
│       ├── arithmetic.py        # Arithmetic perturbation algorithm
│       ├── block_based.py       # Block insert/delete/permute/cross-pollinate
│       └── dictionary.py        # Semantic payload injection
│
├── frontend/
│   ├── index.html               # Dashboard page
│   ├── style.css                # Cybersecurity dark theme
│   └── app.js                   # WebSocket client + UI logic
│
├── seeds/                       # Initial seed corpus
│   ├── sample_config.txt        # Baseline seed
│   ├── near_overflow.txt        # 64-char name (buffer boundary)
│   ├── bad_index.txt            # index=15 (array edge)
│   ├── large_count.txt          # count near INT_MAX
│   ├── format_edge.txt          # Safe format string (%d)
│   └── all_edges.txt            # All fields at boundary simultaneously
│
├── target/
│   ├── vulnerable.cpp           # Intentionally vulnerable C++ source
│   └── vulnerable               # Compiled binary (Mach-O ARM64)
│
└── crash_logs/                  # Auto-generated crash payloads (.bin)
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **C++ compiler** (clang++ or g++)
- **Gemini API key** (for AI strategy analysis)

### 1. Install Dependencies

```bash
cd fuzz-bombardment-engine
pip install -r requirements.txt
pip install httpx python-dotenv
```

### 2. Configure Gemini API Key

```bash
# Edit .env file
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

### 3. Compile the Target Binary

```bash
clang++ -o target/vulnerable -fno-stack-protector -O0 target/vulnerable.cpp
```

### 4. Launch the Engine

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8888
```

### 5. Open the Dashboard

Navigate to **http://localhost:8888** in your browser.

### 6. Run the Workflow

1. Click **🧠 Analyze** — Gemini analyzes the target and selects optimal algorithms
2. Click **▶ Start** — Bombardment begins with AI-selected algorithms
3. Click **■ Stop** — Stops the engine

> **Tip:** You can skip Analyze and click Start directly — it will use all 4 algorithms by default.

---

## 🖥️ Dashboard Features

| Feature | Description |
|---------|-------------|
| **🧠 Gemini Analysis Panel** | Shows Gemini's algorithm selection with colored chips and raw response |
| **Stat Cards** | Live iterations, crash count, crash rate %, exec/sec speed, uptime |
| **Mutation Distribution** | Horizontal bar chart showing execution counts per algorithm |
| **Live Crash Feed** | Real-time crash entries with signal type, algorithm, seed, SHA hash |
| **Activity Console** | Scrolling event log with color-coded crash warnings |
| **Algorithm Dimming** | Unselected algorithms are visually grayed out in the chart |

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serve the dashboard |
| `POST` | `/api/analyze` | Run Gemini strategy analysis on the target |
| `POST` | `/api/start` | Start bombardment (accepts `{ algorithms: [...] }`) |
| `POST` | `/api/stop` | Stop the fuzzing engine |
| `GET` | `/api/stats` | Get current stats snapshot |
| `GET` | `/api/crashes` | List all crash log files |
| `GET` | `/api/seeds` | List seed pool summary |
| `WS` | `/ws` | WebSocket stream for real-time stats + crash events |

### WebSocket Message Types

```json
{ "type": "stats_update",    "data": { "total_iterations": 5000, "crashes_found": 1200, ... } }
{ "type": "crash_event",     "data": { "id": "crash_00042", "signal_name": "SIGSEGV", "algorithm": "bit_flip", ... } }
{ "type": "analysis_result", "data": { "selected_algorithms": ["arithmetic", "block"], "raw_response": "...", "status": "success" } }
{ "type": "log_message",     "data": { "message": "🚀 Engine started..." } }
```

---

## 📊 Performance

Typical results on the included vulnerable target:

| Metric | Value |
|--------|-------|
| **Throughput** | 40–80 exec/sec |
| **Crash Rate** | 25–35% |
| **Time to First Crash** | < 1 second |
| **Unique Crash Signals** | SIGSEGV, SIGBUS, SIGABRT |

---

## 🧠 How Gemini Strategy Selection Works

The engine sends this system prompt to Gemini 2.5 Flash:

```
You are an expert fuzzing strategy engine.

Given a target system: {auto-generated description with source code + seeds}

Available mutation algorithms:
- Bit Flip Mutation
- Arithmetic Mutation
- Block-Based Mutation
- Dictionary-Based Mutation

Analyze the target system's input type and structure, and select only the 
most effective mutation algorithms for maximizing vulnerability discovery.

Output ONLY the selected set of algorithms (no explanation, no extra text).
```

Gemini analyzes the target's:
- **Input format** (key=value text, binary, protocol)
- **Vulnerability types** (buffer overflow, format string, integer bugs)
- **Seed structure** (what fields exist, their sizes and ranges)

And returns only the algorithms that will be most effective — saving CPU cycles by skipping irrelevant mutation strategies.

---

## 📚 References

- Manès, V.J.M., et al. *"The Art, Science, and Engineering of Fuzzing: A Survey."* IEEE TSE, 2019. arXiv:1812.00140
- Google Gemini API Documentation
- AFL (American Fuzzy Lop) — inspiration for mutation strategies
- libFuzzer — structure-aware fuzzing concepts

---


