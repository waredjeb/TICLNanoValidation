You are helping me design/refactor a small, flexible analysis framework for ROOT NanoAOD files produced from CMSSW.

Context:

I have a local repository at:

`~/Projects/NanoAODOffline/`

Inside it there are two ROOT files, both produced by the same NanoAOD ntuplizer:

* `step2.root`: produced from HLT
* `step4_inNANOAODSIM.root`: produced from offline reconstruction

The files are basically identical in structure, but they differ in the collection names.

There is already a first attempt called `TICLNanoValidation`. Please inspect it carefully. In that directory there is also a cloned copy of `law` — Luigi Analysis Framework — so you can inspect the LAW source code and examples if useful.

The goal is to build a clean, small, flexible framework for doing analysis on CMSSW NanoAOD ROOT files.

Main requirements:

1. ROOT / RDataFrame

   * The framework should use ROOT RDataFrame.
   * It should support ROOT implicit multithreading.
   * It should be able to process multiple ROOT files.
   * Ideally it should support splitting work over files/chunks so different tasks can run in parallel.

2. LAW / Luigi / HTCondor

   * The framework should use LAW to define and schedule tasks.
   * It should be possible to run locally.
   * It should be possible to submit tasks to HTCondor.
   * The design should cleanly separate analysis logic from workflow/scheduling logic.

3. Flexibility

   * I want to easily schedule multiple analysis modules.
   * I want to add new modules with minimal boilerplate.
   * I want to run only selected modules when needed.
   * I want modules to be chainable, for example one module computes matching and another module consumes the matching result.

4. Configurability

   * I want to configure as much as possible without editing core code.
   * Examples of configurable things:

     * input files
     * output directory
     * task list / modules to run
     * collection names
     * thresholds
     * binning
     * matching strategy
     * number of threads
     * HTCondor resources
   * Suggest a clean configuration format, for example YAML/TOML/Python config, and explain the tradeoffs.

5. Reco-Sim matching

   * The matching between Reco and Sim objects must be flexible.
   * Different people should be able to add different matching criteria/strategies.
   * However, every matching strategy should return the same standardized output schema, so downstream modules can consume the result without caring which matching algorithm was used.
   * Please propose a clean interface for matching strategies.
   * Please propose a standard matching output format.
   * Please consider that some matching methods may use score thresholds, best-match logic, ΔR, shared energy, association maps, or other criteria.

6. HLT vs Offline collection names

   * Since the HLT and offline NanoAOD files are mostly identical but differ in collection names, the framework should avoid duplicating code.
   * Suggest a clean way to abstract collection names, for example through collection aliases or dataset-specific schemas.
   * I want the same analysis module to work on both files by changing configuration only.

What I want you to do:

Step 1 — Explore

* Inspect the current code base, especially `TICLNanoValidation`.
* Inspect how LAW is currently used, if at all.
* Identify what works well and what is fragile.
* Identify duplicated logic, hardcoded paths, hardcoded collection names, hardcoded thresholds, and places where the design will not scale.

Step 2 — Ask questions before implementation
Before making major changes, ask me clarifying questions. In particular, ask about:

* the expected output of each module,
* whether outputs should be ROOT, Parquet, JSON, pickle, or plots,
* how large the datasets are,
* whether the unit of parallelization should be file-level, event-range-level, module-level, or a combination,
* what matching strategies are already needed,
* what downstream modules should consume the matching result,
* how much backward compatibility with `TICLNanoValidation` is required.

Step 3 — Propose architecture
Propose a clean architecture. Include:

* package layout,
* base classes/interfaces,
* module/plugin system,
* config system,
* dataset/collection schema abstraction,
* matching strategy interface,
* standard matching output schema,
* LAW task layout,
* local execution path,
* HTCondor execution path,
* output directory structure,
* logging/error handling strategy.

Step 4 — Refactoring plan
Give me a staged refactoring plan. Prefer small, reviewable steps:

* minimal working framework,
* one example module,
* one example matching strategy,
* one local LAW task,
* one HTCondor task,
* then extension to multiple modules/files.

Step 5 — Implementation
Only after the design is agreed, implement the changes. When implementing:

* keep the code simple and readable;
* avoid over-engineering;
* write clear base classes;
* write at least one working example module;
* write at least one working matching strategy;
* write example configs for HLT and offline;
* write commands showing how to run locally and via LAW;
* add lightweight tests or smoke tests where possible.

Important design preferences:

* Do not hardcode HLT/offline collection names in analysis code.
* Do not make every module manually parse ROOT branches.
* Do not couple plotting code too tightly to matching code.
* Prefer explicit interfaces over hidden magic.
* Prefer a small framework that is easy to understand over a very abstract one.
* Keep RDataFrame usage central.
* Keep LAW tasks thin: tasks should orchestrate, not contain the physics/analysis logic.
* Matching outputs must be standardized and reusable.

Please start by exploring the repository and summarizing what you find. Then ask me the most important clarifying questions before proposing a final architecture or editing code.





