# Graph Report - CryptoHGNN  (2026-09-12)

## Corpus Check
- 170 files · ~413,231 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1529 nodes · 2779 edges · 205 communities (144 shown, 11 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 62 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Redis Cluster Core
- C Parser Scanner
- Agent Evaluation
- C Parser Node Types
- Crypto Call Detection
- Agents Visualizer
- Node.js Build Tooling
- Pointer Alias Analysis
- Macro Expander
- Tree-sitter C Grammar (Abstract Declarators)
- Rust Parser Scanner
- Security Audit Logger
- CryptoHGNN Model
- Tree-sitter C Grammar (Pointer Declarators)
- Call Graph Builder
- Safe I/O Sandbox
- CryptoGNN Model
- Flow Tracker Graph
- Flow Tracker Classification
- Tree-sitter Node Bindings
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133
- Community 134
- Community 135
- Community 136
- Community 137
- Community 138
- Community 139
- Community 140
- Community 141
- Community 142
- Community 143
- Community 144
- Community 145
- Community 146
- Community 147
- Community 148
- Community 149
- Community 193
- Community 198
- Community 199
- Community 202
- Community 203

## God Nodes (most connected - your core abstractions)
1. `rules` - 115 edges
2. `members` - 43 edges
3. `CParser` - 40 edges
4. `FlowTracker` - 37 edges
5. `WrapperResolver` - 37 edges
6. `AliasAnalyzer` - 36 edges
7. `MacroExpander` - 36 edges
8. `GraphBuilder` - 35 edges
9. `SemanticEngine` - 32 edges
10. `RustParser` - 29 edges

## Surprising Connections (you probably didn't know these)
- `test_non_pointer_copy_not_aliased()` --calls--> `AliasAnalyzer`  [EXTRACTED]
  tests/test_regressions.py → External_scanner/alias_analyzer.py
- `TestFlowTracker` --uses--> `FlowEdge`  [INFERRED]
  tests/test_flow_tracker.py → External_scanner/flow_tracker.py
- `RepoScannerAgent` --uses--> `FlowTracker`  [INFERRED]
  agents/repo_scanner_agent.py → External_scanner/flow_tracker.py
- `RepoScannerAgent` --uses--> `GraphBuilder`  [INFERRED]
  agents/repo_scanner_agent.py → External_scanner/graph_builder.py
- `test_build_graph_handles_unknown_node_types_and_missing_endpoints()` --calls--> `GraphBuilder`  [EXTRACTED]
  tests/test_regressions.py → External_scanner/graph_builder.py

## Import Cycles
- None detected.

## Communities (205 total, 11 thin omitted)

### Community 0 - "Redis Cluster Core"
Cohesion: 0.06
Nodes (111): aeEventLoop, client, clusterLink, clusterMsg, clusterNode, migrateCachedSocket, rio, robj (+103 more)

### Community 1 - "C Parser Scanner"
Cohesion: 0.07
Nodes (38): CryptoFlow Configuration Module Defines ablation toggles, model…, CAssignment, CCall, CFuncDef, CParser, CParseResult, _node_line(), _node_text() (+30 more)

### Community 2 - "Agent Evaluation"
Cohesion: 0.06
Nodes (39): evaluate_agents(), evaluate_agents.py: Evaluates the Agentic AI Remediation layer across 20…, Explainer, Any, Explainer: Developer-friendly vulnerability explainer agent with risk…, Produces developer-oriented explanations of cryptographic flaws with risk…, FixGenerator, Any (+31 more)

### Community 3 - "C Parser Node Types"
Cohesion: 0.08
Nodes (58): CondenseResult, ErrorStatus, Parser, ReusableNode, StackIterateAction, StackPopResult, StackSlice, StackVersion (+50 more)

### Community 4 - "Crypto Call Detection"
Cohesion: 0.05
Nodes (41): find_crypto_call_arguments(), find_literal_variables(), find_runtime_sources(), main(), remove_comments(), scan_file(), _usage_matches_variable(), ArgumentMapping (+33 more)

### Community 5 - "Agents Visualizer"
Cohesion: 0.06
Nodes (38): Any, Data, Tensor, visualizer.py: Generates interactive 3D Plotly visualizations of…, Renders 3D interactive HTML visualizations of interprocedural cryptographic…, Determines the string node type from tensor one-hot or name heuristics., Determines string edge type from edge_attr tensor one-hot., Visualizer (+30 more)

### Community 6 - "Node.js Build Tooling"
Cohesion: 0.04
Nodes (41): eslint, eslint-config-treesitter, node-addon-api, node-gyp-build, prebuildify, tree-sitter, tree-sitter-cli, queries (+33 more)

### Community 7 - "Pointer Alias Analysis"
Cohesion: 0.07
Nodes (22): AliasAnalyzer, PointerAssignment, AliasAnalyzer: Disjoint-set based pointer and alias analysis for C/C++. Tracks…, Extracts pointer assignments using the AST parser: - ptr = &var - ptr1 = ptr2…, Builds alias sets from pointer assignments using the UnionFind data structure., Returns True if var1 and var2 belong to the same alias set., Returns all variables known to alias with the given variable., Connects aliased variables in the FlowTracker global graph with ALIASES edges. (+14 more)

### Community 8 - "Macro Expander"
Cohesion: 0.08
Nodes (23): MacroDefinition, MacroExpander, setter, MacroExpander: C/C++ macro extraction and expansion engine for CryptoFlow.…, Expands all macros in the provided C/C++ source code while preserving line…, Expands a single token / expression if it matches a known macro., Given the position of a macro identifier, checks if it is immediately followed…, Splits code into tokens: STRING, CHAR, COMMENT, IDENTIFIER, SYMBOL. Returns… (+15 more)

### Community 9 - "Tree-sitter C Grammar (Abstract Declarators)"
Cohesion: 0.06
Nodes (36): content, type, value, content, type, value, members, content (+28 more)

### Community 10 - "Rust Parser Scanner"
Cohesion: 0.13
Nodes (14): _node_line(), _node_text(), Any, rust_parser.py: Tree-sitter powered parser for Rust source code (.rs). Extracts…, Filters calls for known Rust crypto crate namespaces (ring, rustls, openssl,…, A `let` binding extracted from the source., Parses Rust source files, extracting AST items, constants, functions, and…, RustCallSite (+6 more)

### Community 11 - "Security Audit Logger"
Cohesion: 0.12
Nodes (19): log_audit_trace(), Writes a timestamped JSON-formatted trace to /data/log/audit_trace.log.…, AnalysisResult, load_crypto_catalog(), Any, SemanticEngine: Master coordinator for CryptoFlow semantic analysis pipeline.…, Executes the full 4-stage sequential semantic pipeline., Master pipeline controller coordinating MacroExpander, WrapperResolver,… (+11 more)

### Community 12 - "CryptoHGNN Model"
Cohesion: 0.13
Nodes (18): Data, Tensor, CryptoHGNN: Full model combining Hyperbolic Graph Neural Network (curvature…, Data, Tensor, GenericHGNN: 3-layer Hyperbolic Graph Neural Network with curvature c=1.0 on…, exp_map_zero(), HyperbolicLinear (+10 more)

### Community 13 - "Tree-sitter C Grammar (Pointer Declarators)"
Cohesion: 0.09
Nodes (30): content, type, value, content, type, value, content, type (+22 more)

### Community 14 - "Call Graph Builder"
Cohesion: 0.14
Nodes (14): CallGraphBuilder, CallSite, FunctionDef, CallGraph: Inter-procedural CallGraphBuilder for C/C++ source trees. Extracts…, Resolves each call site to its FunctionDef target, resolving indirect calls if…, Resolves function pointer calls through alias chains (fp -> target) up to…, Returns directed call graph as {caller: {callee1, callee2, ...}}., Extracts and resolves direct and indirect function calls across multiple C/C++… (+6 more)

### Community 15 - "Safe I/O Sandbox"
Cohesion: 0.12
Nodes (22): Any, safe_io.py: Safe on-disk serialization helpers. Pytorch Geometric ``Data``…, Load a Pytorch Geometric ``Data`` graph without arbitrary code execution., _register_safe_globals(), safe_load_graph(), CryptoHGNN, Crypto-HGNN: Core proposed model combining hyperbolic geometry on the Poincaré…, attention_analysis.py: Analyzes node attention weights produced by CryptoHGNN… (+14 more)

### Community 16 - "CryptoGNN Model"
Cohesion: 0.13
Nodes (20): CryptoGNN, CryptoGNN: 3-layer Graph Convolutional Network utilizing full crypto-semantic…, 3-layer GCN model trained on crypto-semantic graph features with attention-…, mask_feature_columns(), mask_structure(), Data, _random_edge_graphs(), ablation_study.py: Evaluates 7 ablation configurations of CryptoFlow to isolate… (+12 more)

### Community 17 - "Flow Tracker Graph"
Cohesion: 0.11
Nodes (12): FlowGraph, FlowNode, Any, Returns target ids (and distinct target names) for outgoing edges from key., Computes the shortest path from source to sink in the flow graph using BFS., Tracks argument-to-parameter dataflow for a function invocation. Supports both…, Track return value from function: func -> return_expr., Tracks return value from callee to caller variable. (+4 more)

### Community 18 - "Flow Tracker Classification"
Cohesion: 0.14
Nodes (15): FlowTracker, Dataflow analysis tracking assignments, parameter passing, return values,…, Tracks dataflow from rhs expression to lhs variable., Test function call argument tracking., Test return value tracking., Test struct field access tracking., Test evidence path construction., Test variable assignment tracking. (+7 more)

### Community 19 - "Tree-sitter Node Bindings"
Cohesion: 0.12
Nodes (16): Env, Object, PyMODINIT_FUNC, PyObject, Init(), TSLanguage, _binding_language(), PyInit__binding() (+8 more)

### Community 20 - "Community 20"
Cohesion: 0.31
Nodes (19): adjust_size(), alloc_fwd(), alloc_rev(), bin_index(), bin_index_up(), __dump_heap(), expand_heap(), first_set() (+11 more)

### Community 21 - "Community 21"
Cohesion: 0.21
Nodes (13): add_manual_and_day5(), build_juliet_groups(), group_files_by_prefix(), main(), manifest_path(), Path, audit_juliet.py: Discovers and groups Juliet test files into interprocedural…, Add hand-labeled test cases from manual_tests/ and Day5_test/. (+5 more)

### Community 22 - "Community 22"
Cohesion: 0.18
Nodes (5): EdgeTypeStr, FlowEdge, str, FlowTracker: Tracks intra- and inter-procedural dataflows, struct/array…, String subclass that compares case-insensitively for edge types.

### Community 23 - "Community 23"
Cohesion: 0.21
Nodes (8): fixture, GenericGNN, Data, Tensor, GenericGNN: 3-layer Graph Convolutional Network (GCN) baseline on generic code…, 3-layer GCN model for binary cryptographic misuse detection. Uses generic…, sample_graph(), test_generic_gnn()

### Community 24 - "Community 24"
Cohesion: 0.29
Nodes (10): DataLoader, evaluate_split(), load_dataset_by_split(), Data, Module, Path, train.py: End-to-end training pipeline for CryptoFlow models. Trains…, train_all_models() (+2 more)

### Community 25 - "Community 25"
Cohesion: 0.31
Nodes (3): NodeDict, dict, Dictionary that indexes FlowNodes by id, and allows lookup by name/value.

### Community 26 - "Community 26"
Cohesion: 0.33
Nodes (5): bdist_wheel, egg_info, BdistWheel, Build, EggInfo

### Community 27 - "Community 27"
Cohesion: 0.33
Nodes (5): GenericHGNN, 3-layer Hyperbolic GNN operating on the Poincaré ball model with curvature c =…, HyperbolicGraphConv, Hyperbolic Graph Convolution Layer. Aggregates neighbor features in tangent…, test_generic_hgnn()

### Community 28 - "Community 28"
Cohesion: 0.22
Nodes (9): bindings, c, go, java, node, python, rust, swift (+1 more)

### Community 29 - "Community 29"
Cohesion: 0.25
Nodes (4): GraphifyParser, Any, Parses graphify output and returns nodes and edges., Integrates Graphify nodes and edges into the given FlowGraph.

### Community 30 - "Community 30"
Cohesion: 0.29
Nodes (5): LanguageFn, HIGHLIGHT_QUERY, LANGUAGE, NODE_TYPES, TAGS_QUERY

### Community 31 - "Community 31"
Cohesion: 0.38
Nodes (5): commaSep(), commaSep1(), PREC, preprocessor(), preprocIf()

### Community 32 - "Community 32"
Cohesion: 0.29
Nodes (7): repository, metadata, authors, description, license, links, version

### Community 33 - "Community 33"
Cohesion: 0.60
Nodes (5): collect_source_files(), extract_number(), extract_verdict(), main(), scan_file()

### Community 34 - "Community 34"
Cohesion: 0.33
Nodes (4): testing.T, unsafe.Pointer, Language(), TestCanLoadGrammar()

### Community 35 - "Community 35"
Cohesion: 0.40
Nodes (5): members, type, rules, if_statement, preproc_argument_list

### Community 36 - "Community 36"
Cohesion: 0.83
Nodes (3): inner_crypto_layer_1(), intermediate_wrapper_1(), service_handler_1()

### Community 37 - "Community 37"
Cohesion: 0.83
Nodes (3): inner_crypto_layer_2(), intermediate_wrapper_2(), service_handler_2()

### Community 38 - "Community 38"
Cohesion: 0.83
Nodes (3): inner_crypto_layer_3(), intermediate_wrapper_3(), service_handler_3()

### Community 39 - "Community 39"
Cohesion: 0.83
Nodes (3): inner_crypto_layer_4(), intermediate_wrapper_4(), service_handler_4()

### Community 40 - "Community 40"
Cohesion: 0.83
Nodes (3): inner_crypto_layer_5(), intermediate_wrapper_5(), service_handler_5()

### Community 41 - "Community 41"
Cohesion: 0.83
Nodes (3): inner_crypto_layer_6(), intermediate_wrapper_6(), service_handler_6()

### Community 42 - "Community 42"
Cohesion: 0.83
Nodes (3): inner_crypto_layer_7(), intermediate_wrapper_7(), service_handler_7()

### Community 43 - "Community 43"
Cohesion: 0.83
Nodes (3): inner_crypto_layer_8(), intermediate_wrapper_8(), service_handler_8()

### Community 44 - "Community 44"
Cohesion: 0.83
Nodes (3): inner_crypto_layer_9(), intermediate_wrapper_9(), service_handler_9()

### Community 45 - "Community 45"
Cohesion: 0.83
Nodes (3): inner_crypto_layer_10(), intermediate_wrapper_10(), service_handler_10()

### Community 46 - "Community 46"
Cohesion: 0.50
Nodes (3): BaseNode, ChildNode, NodeInfo

### Community 47 - "Community 47"
Cohesion: 0.50
Nodes (3): name, $schema, word

### Community 48 - "Community 48"
Cohesion: 0.50
Nodes (4): content, type, value, abstract_array_declarator

### Community 49 - "Community 49"
Cohesion: 0.50
Nodes (4): content, type, value, array_declarator

### Community 50 - "Community 50"
Cohesion: 0.50
Nodes (4): content, type, value, array_field_declarator

### Community 51 - "Community 51"
Cohesion: 0.50
Nodes (4): content, type, value, array_type_declarator

### Community 52 - "Community 52"
Cohesion: 0.50
Nodes (4): content, type, value, attributed_declarator

### Community 53 - "Community 53"
Cohesion: 0.50
Nodes (4): content, type, value, attributed_field_declarator

### Community 54 - "Community 54"
Cohesion: 0.50
Nodes (4): content, type, value, attributed_type_declarator

### Community 55 - "Community 55"
Cohesion: 0.50
Nodes (4): name, translation_unit, content, type

### Community 56 - "Community 56"
Cohesion: 0.50
Nodes (4): content, type, value, _declaration_specifiers

### Community 57 - "Community 57"
Cohesion: 0.50
Nodes (4): content, type, value, _function_declaration_declarator

### Community 58 - "Community 58"
Cohesion: 0.50
Nodes (4): content, type, value, function_type_declarator

### Community 59 - "Community 59"
Cohesion: 0.50
Nodes (4): content, type, value, parenthesized_declarator

### Community 60 - "Community 60"
Cohesion: 0.50
Nodes (4): content, type, value, parenthesized_type_declarator

### Community 61 - "Community 61"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_call_expression

### Community 62 - "Community 62"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_elif

### Community 63 - "Community 63"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_elif_in_enumerator_list_no_comma

### Community 64 - "Community 64"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_elif_in_field_declaration_list

### Community 65 - "Community 65"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_elifdef

### Community 66 - "Community 66"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_elifdef_in_enumerator_list

### Community 67 - "Community 67"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_elifdef_in_enumerator_list_no_comma

### Community 68 - "Community 68"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_elifdef_in_field_declaration_list

### Community 69 - "Community 69"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_else_in_enumerator_list

### Community 70 - "Community 70"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_else_in_enumerator_list_no_comma

### Community 71 - "Community 71"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_if

### Community 72 - "Community 72"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_if_in_enumerator_list

### Community 73 - "Community 73"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_if_in_enumerator_list_no_comma

### Community 74 - "Community 74"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_if_in_field_declaration_list

### Community 75 - "Community 75"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_ifdef

### Community 76 - "Community 76"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_ifdef_in_enumerator_list

### Community 77 - "Community 77"
Cohesion: 0.50
Nodes (4): content, type, value, preproc_unary_expression

### Community 78 - "Community 78"
Cohesion: 0.50
Nodes (4): struct_specifier, content, type, value

### Community 79 - "Community 79"
Cohesion: 0.50
Nodes (4): union_specifier, content, type, value

### Community 85 - "Community 85"
Cohesion: 0.67
Nodes (3): members, type, _abstract_declarator

### Community 86 - "Community 86"
Cohesion: 0.67
Nodes (3): members, type, alignas_qualifier

### Community 87 - "Community 87"
Cohesion: 0.67
Nodes (3): members, type, attribute_declaration

### Community 88 - "Community 88"
Cohesion: 0.67
Nodes (3): members, type, attribute

### Community 89 - "Community 89"
Cohesion: 0.67
Nodes (3): members, type, attribute_specifier

### Community 90 - "Community 90"
Cohesion: 0.67
Nodes (3): members, type, attributed_statement

### Community 91 - "Community 91"
Cohesion: 0.67
Nodes (3): members, type, bitfield_clause

### Community 92 - "Community 92"
Cohesion: 0.67
Nodes (3): members, type, _block_item

### Community 93 - "Community 93"
Cohesion: 0.67
Nodes (3): members, type, compound_statement

### Community 94 - "Community 94"
Cohesion: 0.67
Nodes (3): members, type, _declaration_declarator

### Community 95 - "Community 95"
Cohesion: 0.67
Nodes (3): members, type, declaration_list

### Community 96 - "Community 96"
Cohesion: 0.67
Nodes (3): members, type, declaration

### Community 97 - "Community 97"
Cohesion: 0.67
Nodes (3): members, type, _declaration_modifiers

### Community 98 - "Community 98"
Cohesion: 0.67
Nodes (3): members, type, _declarator

### Community 99 - "Community 99"
Cohesion: 0.67
Nodes (3): members, type, enum_specifier

### Community 100 - "Community 100"
Cohesion: 0.67
Nodes (3): members, type, enumerator_list

### Community 101 - "Community 101"
Cohesion: 0.67
Nodes (3): members, type, enumerator

### Community 102 - "Community 102"
Cohesion: 0.67
Nodes (3): members, type, expression_statement

### Community 103 - "Community 103"
Cohesion: 0.67
Nodes (3): members, type, _field_declaration_declarator

### Community 104 - "Community 104"
Cohesion: 0.67
Nodes (3): members, type, _field_declaration_list_item

### Community 105 - "Community 105"
Cohesion: 0.67
Nodes (3): members, type, field_declaration_list

### Community 106 - "Community 106"
Cohesion: 0.67
Nodes (3): members, type, field_declaration

### Community 107 - "Community 107"
Cohesion: 0.67
Nodes (3): members, type, _field_declarator

### Community 108 - "Community 108"
Cohesion: 0.67
Nodes (3): members, type, function_definition

### Community 109 - "Community 109"
Cohesion: 0.67
Nodes (3): members, type, init_declarator

### Community 110 - "Community 110"
Cohesion: 0.67
Nodes (3): members, type, labeled_statement

### Community 111 - "Community 111"
Cohesion: 0.67
Nodes (3): members, type, linkage_specification

### Community 112 - "Community 112"
Cohesion: 0.67
Nodes (3): members, type, ms_based_modifier

### Community 113 - "Community 113"
Cohesion: 0.67
Nodes (3): members, type, ms_call_modifier

### Community 114 - "Community 114"
Cohesion: 0.67
Nodes (3): members, type, ms_declspec_modifier

### Community 115 - "Community 115"
Cohesion: 0.67
Nodes (3): members, type, ms_pointer_modifier

### Community 116 - "Community 116"
Cohesion: 0.67
Nodes (3): type, value, ms_restrict_modifier

### Community 117 - "Community 117"
Cohesion: 0.67
Nodes (3): type, value, ms_signed_ptr_modifier

### Community 118 - "Community 118"
Cohesion: 0.67
Nodes (3): members, type, ms_unaligned_ptr_modifier

### Community 119 - "Community 119"
Cohesion: 0.67
Nodes (3): type, value, ms_unsigned_ptr_modifier

### Community 120 - "Community 120"
Cohesion: 0.67
Nodes (3): members, type, _non_case_statement

### Community 121 - "Community 121"
Cohesion: 0.67
Nodes (3): members, type, _old_style_function_declarator

### Community 122 - "Community 122"
Cohesion: 0.67
Nodes (3): members, type, _old_style_function_definition

### Community 123 - "Community 123"
Cohesion: 0.67
Nodes (3): members, type, _old_style_parameter_list

### Community 124 - "Community 124"
Cohesion: 0.67
Nodes (3): members, type, parameter_declaration

### Community 125 - "Community 125"
Cohesion: 0.67
Nodes (3): members, type, parameter_list

### Community 126 - "Community 126"
Cohesion: 0.67
Nodes (3): members, type, preproc_binary_expression

### Community 127 - "Community 127"
Cohesion: 0.67
Nodes (3): members, type, preproc_call

### Community 128 - "Community 128"
Cohesion: 0.67
Nodes (3): members, type, preproc_def

### Community 129 - "Community 129"
Cohesion: 0.67
Nodes (3): members, type, preproc_defined

### Community 130 - "Community 130"
Cohesion: 0.67
Nodes (3): type, value, preproc_directive

### Community 131 - "Community 131"
Cohesion: 0.67
Nodes (3): members, type, _preproc_expression

### Community 132 - "Community 132"
Cohesion: 0.67
Nodes (3): members, type, preproc_function_def

### Community 133 - "Community 133"
Cohesion: 0.67
Nodes (3): members, type, preproc_include

### Community 134 - "Community 134"
Cohesion: 0.67
Nodes (3): members, type, preproc_params

### Community 135 - "Community 135"
Cohesion: 0.67
Nodes (3): members, type, preproc_parenthesized_expression

### Community 136 - "Community 136"
Cohesion: 0.67
Nodes (3): sized_type_specifier, members, type

### Community 137 - "Community 137"
Cohesion: 0.67
Nodes (3): statement, members, type

### Community 138 - "Community 138"
Cohesion: 0.67
Nodes (3): storage_class_specifier, members, type

### Community 139 - "Community 139"
Cohesion: 0.67
Nodes (3): _top_level_expression_statement, members, type

### Community 140 - "Community 140"
Cohesion: 0.67
Nodes (3): _top_level_item, members, type

### Community 141 - "Community 141"
Cohesion: 0.67
Nodes (3): _top_level_statement, members, type

### Community 142 - "Community 142"
Cohesion: 0.67
Nodes (3): _type_declarator, members, type

### Community 143 - "Community 143"
Cohesion: 0.67
Nodes (3): type_definition, members, type

### Community 144 - "Community 144"
Cohesion: 0.67
Nodes (3): _type_definition_declarators, members, type

### Community 145 - "Community 145"
Cohesion: 0.67
Nodes (3): _type_definition_type, members, type

### Community 146 - "Community 146"
Cohesion: 0.67
Nodes (3): type_qualifier, members, type

### Community 147 - "Community 147"
Cohesion: 0.67
Nodes (3): type_specifier, members, type

### Community 148 - "Community 148"
Cohesion: 0.67
Nodes (3): variadic_parameter, type, value

## Knowledge Gaps
- **290 isolated node(s):** `tree-sitter-c`, `PackageDescription`, `BaseNode`, `ChildNode`, `NodeInfo` (+285 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 628 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CParser` connect `C Parser Scanner` to `C Parser Node Types`, `Crypto Call Detection`, `Agents Visualizer`, `Pointer Alias Analysis`, `Security Audit Logger`, `Call Graph Builder`, `Flow Tracker Graph`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Why does `rules` connect `Community 35` to `Tree-sitter C Grammar (Abstract Declarators)`, `Tree-sitter C Grammar (Pointer Declarators)`, `Community 47`, `Community 48`, `Community 49`, `Community 50`, `Community 51`, `Community 52`, `Community 53`, `Community 54`, `Community 55`, `Community 56`, `Community 57`, `Community 58`, `Community 59`, `Community 60`, `Community 61`, `Community 62`, `Community 63`, `Community 64`, `Community 65`, `Community 66`, `Community 67`, `Community 68`, `Community 69`, `Community 70`, `Community 71`, `Community 72`, `Community 73`, `Community 74`, `Community 75`, `Community 76`, `Community 77`, `Community 78`, `Community 79`, `Community 85`, `Community 86`, `Community 87`, `Community 88`, `Community 89`, `Community 90`, `Community 91`, `Community 92`, `Community 93`, `Community 94`, `Community 95`, `Community 96`, `Community 97`, `Community 98`, `Community 99`, `Community 100`, `Community 101`, `Community 102`, `Community 103`, `Community 104`, `Community 105`, `Community 106`, `Community 107`, `Community 108`, `Community 109`, `Community 110`, `Community 111`, `Community 112`, `Community 113`, `Community 114`, `Community 115`, `Community 116`, `Community 117`, `Community 118`, `Community 119`, `Community 120`, `Community 121`, `Community 122`, `Community 123`, `Community 124`, `Community 125`, `Community 126`, `Community 127`, `Community 128`, `Community 129`, `Community 130`, `Community 131`, `Community 132`, `Community 133`, `Community 134`, `Community 135`, `Community 136`, `Community 137`, `Community 138`, `Community 139`, `Community 140`, `Community 141`, `Community 142`, `Community 143`, `Community 144`, `Community 145`, `Community 146`, `Community 147`, `Community 148`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Why does `WrapperResolver` connect `Crypto Call Detection` to `C Parser Scanner`, `Agent Evaluation`, `Agents Visualizer`, `Security Audit Logger`, `Flow Tracker Graph`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `CParser` (e.g. with `AliasAnalyzer` and `CallGraphBuilder`) actually correct?**
  _`CParser` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `FlowTracker` (e.g. with `RepoScannerAgent` and `GraphBuilder`) actually correct?**
  _`FlowTracker` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `tree-sitter-c`, `PackageDescription`, `BaseNode` to the rest of the system?**
  _290 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Redis Cluster Core` be split into smaller, more focused modules?**
  _Cohesion score 0.058944374209860935 - nodes in this community are weakly interconnected._