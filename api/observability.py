import uuid
import time
from typing import Dict, List, Any, Optional

# Global registry of active/completed runs
# Format: { run_id: { "status": str, "scenario": str, "snapshots": [dict], "scorecard": dict } }
execution_runs: Dict[str, Any] = {}

def create_run(scenario: str) -> str:
    run_id = str(uuid.uuid4())
    execution_runs[run_id] = {
        "run_id": run_id,
        "scenario": scenario,
        "status": "RUNNING",
        "created_at": time.time(),
        "snapshots": [],
        "scorecard": {}
    }
    
    # Pre-populate progressive snapshots based on the scenario
    # This guarantees high-fidelity, immediate explainability data for the presenter
    populate_scenario_snapshots(run_id, scenario)
    return run_id

def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    return execution_runs.get(run_id)

def list_runs() -> List[Dict[str, Any]]:
    return [
        {
            "run_id": r_id,
            "scenario": r_data["scenario"],
            "status": r_data["status"],
            "created_at": r_data["created_at"],
            "snapshots_count": len(r_data["snapshots"])
        }
        for r_id, r_data in execution_runs.items()
    ]

def add_custom_snapshot(run_id: str, state_dict: dict):
    if run_id in execution_runs:
        execution_runs[run_id]["snapshots"].append(state_dict)

def complete_run(run_id: str, scorecard: dict):
    if run_id in execution_runs:
        execution_runs[run_id]["status"] = "COMPLETED"
        execution_runs[run_id]["scorecard"] = scorecard

def populate_scenario_snapshots(run_id: str, scenario: str):
    # We define 10 progressive steps (0s to 120s) for the narration timeline
    snapshots = []
    
    # Common agents list
    agents_list = [
        {"name": "PlannerAgent", "role": "Orchestrator", "status": "WAITING", "confidence": 1.0},
        {"name": "CarbonCalculationAgent", "role": "Worker", "status": "WAITING", "confidence": 1.0},
        {"name": "SupplierAgent", "role": "Worker", "status": "WAITING", "confidence": 1.0},
        {"name": "ComplianceAgent", "role": "Worker", "status": "WAITING", "confidence": 1.0},
        {"name": "OptimizationAgent", "role": "Worker", "status": "WAITING", "confidence": 1.0},
        {"name": "ReflectionAgent", "role": "Verification", "status": "WAITING", "confidence": 1.0},
        {"name": "ConversationAgent", "role": "Output", "status": "WAITING", "confidence": 1.0},
        {"name": "CertificationAgent", "role": "A2A", "status": "WAITING", "confidence": 1.0},
        {"name": "TransportAgent", "role": "Logistics", "status": "WAITING", "confidence": 1.0}
    ]

    # SCENARIO 1: A2A Federation & Negotiation
    if scenario == "a2a_federation":
        # 10 steps representing the Demo Director timeline
        for step in range(10):
            timestamp = f"09:{step:02d}"
            
            # Progress status
            status_map = ["PLANNING", "NEGOTIATING", "DISCOVERING_TOOLS", "CALCULATING", "CONSENSUS", "CRITIQUE", "REFLECTION", "RECOVERY", "COMPLETED", "COMPLETED"]
            current_status = status_map[min(step, len(status_map)-1)]
            
            # Confidence evolution
            confidences = [0.80, 0.73, 0.75, 0.74, 0.74, 0.68, 0.65, 0.92, 0.95, 0.95]
            overall_confidence = confidences[step]
            
            # Narrative Timeline Milestone
            narratives = [
                {"time": "09:00", "message": "Planner analyzed objective: calculate emissions for A2A federated suppliers.", "type": "planner", "explanation": "Planner decomposes the query and identifies that remote suppliers need to be contacted for direct Scope 3 carbon values instead of using national estimates."},
                {"time": "09:01", "message": "Supplier C refused Scope 3 access due to data privacy policies.", "type": "a2a", "explanation": "Supplier C denied the initial federated query because it contains confidential process intensity logs. Triggering A2A negotiation."},
                {"time": "09:02", "message": "Planner initiated negotiation with Supplier C via A2A protocol.", "type": "a2a", "explanation": "SupplierAgent exchanges credentials and proposes a hashed/aggregated carbon intensity protocol, agreeing on partial data access."},
                {"time": "09:03", "message": "Negotiation succeeded; Supplier C shared limited disclosure permissions.", "type": "a2a", "explanation": "Supplier C accepted the aggregated protocol. A2A session successfully authenticated with trust score re-calibrated."},
                {"time": "09:04", "message": "Carbon Calculation Agent completed emissions run using direct supplier numbers.", "type": "tool", "explanation": "Emissions for Supplier A and C are calculated. Supplier B's data is verified using FastMCP registry tools."},
                {"time": "09:05", "message": "Consensus Engine initiated cross-validation of emissions evidence.", "type": "consensus", "explanation": "All worker agents evaluate supplier inputs. Consensus Engine compiles opinions with an initial score of 78%."},
                {"time": "09:06", "message": "Compliance Agent raised critique: Supplier B's emissions are estimated, not verified.", "type": "reflection", "explanation": "Compliance checks detect that Supplier B's cargo records are regional averages rather than direct carbon readings. Triggering Reflection layer."},
                {"time": "09:07", "message": "Reflection Agent detected variance, recommending Certification verification.", "type": "reflection", "explanation": "Self-reflection classifies the missing verification as a high risk. It schedules an autonomous recovery action to query CertificationAgent."},
                {"time": "09:08", "message": "Certification Agent verified Supplier B's green certificate, improving confidence to 92%.", "type": "recovery", "explanation": "Autonomous recovery successfully pulls active certification keys, replacing fallback estimates with verified direct factors."},
                {"time": "09:09", "message": "Final report generated with verified green stamp. Compliance approved.", "type": "success", "explanation": "Goal complete. Execution report generated with 100% task completion and verified Scope 3 certification."}
            ]
            
            # Active agent highlights for visual focus
            active_agents = ["PlannerAgent", "SupplierAgent", "SupplierAgent", "SupplierAgent", "CarbonCalculationAgent", "SupplierAgent", "ComplianceAgent", "ReflectionAgent", "CertificationAgent", "ConversationAgent"]
            current_active = active_agents[step]
            
            # Tasks list
            tasks = [
                {"task_id": "discover_cards", "assigned_agent": "SupplierAgent", "execution_status": "COMPLETED" if step > 0 else "RUNNING", "confidence": 0.98, "execution_time": 0.8},
                {"task_id": "a2a_supplier_handshakes", "assigned_agent": "SupplierAgent", "execution_status": "COMPLETED" if step > 2 else ("RUNNING" if step in [1, 2] else "PENDING"), "confidence": 0.95, "execution_time": 1.4},
                {"task_id": "run_consensus", "assigned_agent": "SupplierAgent", "execution_status": "COMPLETED" if step > 4 else ("RUNNING" if step in [3, 4] else "PENDING"), "confidence": 0.78 if step < 7 else 0.95, "execution_time": 1.2},
                {"task_id": "run_calc", "assigned_agent": "CarbonCalculationAgent", "execution_status": "COMPLETED" if step > 5 else ("RUNNING" if step == 5 else "PENDING"), "confidence": 0.95, "execution_time": 0.6},
                {"task_id": "run_audit", "assigned_agent": "ComplianceAgent", "execution_status": "COMPLETED" if step > 6 else ("RUNNING" if step == 6 else "PENDING"), "confidence": 0.90, "execution_time": 0.9},
                {"task_id": "reflection_run", "assigned_agent": "ReflectionAgent", "execution_status": "COMPLETED" if step > 7 else ("RUNNING" if step == 7 else "PENDING"), "confidence": 0.95, "execution_time": 1.1},
                {"task_id": "run_optimize", "assigned_agent": "OptimizationAgent", "execution_status": "COMPLETED" if step > 8 else ("RUNNING" if step == 8 else "PENDING"), "confidence": 0.92, "execution_time": 0.7},
                {"task_id": "generate_response", "assigned_agent": "ConversationAgent", "execution_status": "COMPLETED" if step > 8 else ("RUNNING" if step == 9 else "PENDING"), "confidence": 0.98, "execution_time": 0.5}
            ]
            
            # A2A Trust Scores
            trust_scores = {
                "Supplier A Corp": 0.98,
                "Supplier B Corp": 0.85 if step < 8 else 0.95,
                "Supplier C Corp": 0.75 if step < 3 else 0.90,
                "Certification_Authority": 1.0
            }
            
            # Quality scores dictionary
            quality = {
                "Planning": 0.95,
                "Execution": 0.70 if step < 7 else 0.94,
                "Evidence": 0.60 if step < 8 else 0.95,
                "Consensus": 0.78 if step < 6 else 0.94,
                "Overall": overall_confidence
            }
            
            # State snapshot creation
            snap = {
                "step": step,
                "current_status": current_status,
                "overall_confidence": overall_confidence,
                "active_agent": current_active,
                "narrative_timeline": narratives[:step+1],
                "latest_narrative": narratives[step],
                "tasks": tasks,
                "a2a_trust_scores": trust_scores,
                "quality_scores": quality,
                "a2a_sessions": {
                    "Supplier C Corp": {
                        "session_id": "sess_c_9910",
                        "auth_state": "AUTHENTICATED" if step > 2 else "AUTHENTICATING",
                        "permission_grants": ["Scope3_Intensity_Aggregated"] if step > 2 else [],
                        "negotiation_state": "RESOLVED" if step > 2 else "PROPOSING_HASHED_SCHEME",
                        "conversation_history": [
                            {"sender": "SupplierAgent", "recipient": "Supplier C Corp", "request_type": "DataQuery", "payload": "Scope3_Carbon_Direct"},
                            {"sender": "Supplier C Corp", "recipient": "SupplierAgent", "request_type": "Denial", "payload": "Confidentiality Restriction"},
                            {"sender": "SupplierAgent", "recipient": "Supplier C Corp", "request_type": "ProposeHash", "payload": "Aggregate_CO2_Only"}
                        ] if step > 1 else []
                    }
                },
                "mcp_discovery_events": [
                    {"agent_name": "CarbonCalculationAgent", "query": "get_supplier_carbon_status", "discovered_tools": ["get_supplier_carbon_status"], "timestamp": time.time()}
                ] if step > 2 else [],
                "mcp_selection_decisions": [
                    {"agent_name": "CarbonCalculationAgent", "selected_tool": "get_supplier_carbon_status", "reasoning": "Selected get_supplier_carbon_status because it query is direct index match.", "timestamp": time.time()}
                ] if step > 2 else [],
                "reflection_events": [
                    {
                        "stage": "Task",
                        "detected_failure": "Estimation Variance Warning",
                        "severity": "HIGH",
                        "root_cause": "Supplier B carbon parameters are estimated regional grid intensity rather than direct manifests, causing 23% potential variance.",
                        "confidence_change": {"before": 0.68, "after": 0.92},
                        "recovery_action": "Query CertificationAgent for active supplier environmental audits.",
                        "summary": "ComplianceAgent flagged estimates. Reflection matched Supplier B to active CBAM certified registries."
                    }
                ] if step > 6 else [],
                "goal_model": {
                    "goal_id": "goal_a2a_federation",
                    "user_intent": "calculate emissions for A2A federated suppliers",
                    "desired_outcome": "Verify Scope 3 carbon footprints across federated suppliers and apply CBAM compliance.",
                    "success_criteria": ["All supplier handshakes resolved", "Trust metrics updated", "Consensus verified"],
                    "remaining_unknowns": ["Supplier B direct factors"] if step < 8 else []
                },
                "planning_hypothesis": {
                    "hypotheses": [
                        {"hypothesis_text": "H1: Connect with remote organizations, negotiate Supplier C block, cross-validate evidence.", "confidence": 0.98, "selected": True}
                    ],
                    "selected_hypothesis_index": 0,
                    "discarded_hypotheses": []
                },
                "decision_journal": [
                    {"timestamp": "09:00", "decision": "PLAN_INITIALIZED", "reason": "Formulated task DAG targeting Supplier A, B, and C.", "evidence": "User Goal", "confidence": 1.0, "alternative_considered": [], "expected_outcome": "Unprocessed shipments calculated"}
                ]
            }
            snapshots.append(snap)
            
        execution_runs[run_id]["snapshots"] = snapshots
        execution_runs[run_id]["scorecard"] = {
            "mission_success": "COMPLETED (100%)",
            "overall_confidence": "95%",
            "recovered_issues": "1 (Supplier B verification)",
            "autonomous_decisions": "2 replannings",
            "organizations_contacted": "3 remote orgs",
            "agents_used": "9 agents",
            "mcp_tools_used": "5 tools",
            "negotiations_completed": "1 (Supplier C scheme)",
            "consensus_score": "95%",
            "reflection_improvements": "+27% confidence",
            "execution_time": "5.6s",
            "carbon_saved": "1,420 tCO2",
            "compliance_risk_reduced": "85% reduction",
            "quality_score": "9.6/10"
        }

    # SCENARIO 2: MCP Tool Discovery & Fallback
    elif scenario == "mcp_discovery":
        for step in range(10):
            timestamp = f"10:{step:02d}"
            status_map = ["PLANNING", "DISCOVERING_TOOLS", "DISCOVERING_TOOLS", "SELECTION", "CALCULATING", "FALLBACK_TRIGGERED", "FALLBACK_RESOLVED", "VALIDATING", "COMPLETED", "COMPLETED"]
            current_status = status_map[min(step, len(status_map)-1)]
            confidences = [0.90, 0.92, 0.88, 0.85, 0.85, 0.70, 0.94, 0.94, 0.96, 0.96]
            overall_confidence = confidences[step]
            
            narratives = [
                {"time": "10:00", "message": "Planner started objective: discover emissions calculation tools.", "type": "planner", "explanation": "Planner decomposes user goal to run CBAM audit cycles and discovers available registry tools."},
                {"time": "10:01", "message": "Carbon Calculation Agent queried MCP Registry for supplier factors.", "type": "tool", "explanation": "Agent initiates a discovery search query on local and remote tool servers for 'Scope 3 carbon values'."},
                {"time": "10:02", "message": "Discovered candidate tool: `get_supplier_carbon_status`.", "type": "tool", "explanation": "Registry returned get_supplier_carbon_status tool, which fetches direct manufacturer declarations."},
                {"time": "10:03", "message": "Carbon Calculation Agent selected get_supplier_carbon_status based on reliability score.", "type": "tool", "explanation": "Heuristic selection chosen because it has a reliability score of 98% and is expected to provide direct readings."},
                {"time": "10:04", "message": "Executing get_supplier_carbon_status: Supplier B factors are missing in DB.", "type": "tool", "explanation": "Tool returned None for Supplier B. The direct emission factor is unavailable in the database."},
                {"time": "10:05", "message": "Fallback tool discovered: `compute_regional_grid_intensity`.", "type": "tool", "explanation": "Tool registry fallback chain identifies regional grid average calculations as an acceptable fallback schema."},
                {"time": "10:06", "message": "Executed regional grid average intensity (Fallback factor applied: 0.42 tCO2/MWh).", "type": "tool", "explanation": "Grid average applied successfully. Carbon calculations completed with fallback parameters."},
                {"time": "10:07", "message": "Tool output validation completed. Validated 250 tonnes Coil emissions.", "type": "tool", "explanation": "Validation layer evaluates results against CBAM schema compliance, reporting output structure is correct."},
                {"time": "10:08", "message": "Compliance Agent audited fallback calculations. CBAM tariffs compiled.", "type": "consensus", "explanation": "CBAM duties are calculated on fallback emissions. Compliance files tariff reports."},
                {"time": "10:09", "message": "Final report generated. Emissions forecast compiled.", "type": "success", "explanation": "Goal complete. Final summary compiled for presenter."}
            ]
            
            active_agents = ["PlannerAgent", "CarbonCalculationAgent", "CarbonCalculationAgent", "CarbonCalculationAgent", "CarbonCalculationAgent", "CarbonCalculationAgent", "CarbonCalculationAgent", "CarbonCalculationAgent", "ComplianceAgent", "ConversationAgent"]
            current_active = active_agents[min(step, len(active_agents)-1)]
            
            tasks = [
                {"task_id": "run_calc", "assigned_agent": "CarbonCalculationAgent", "execution_status": "COMPLETED" if step > 6 else "RUNNING", "confidence": 0.95, "execution_time": 1.2},
                {"task_id": "run_audit", "assigned_agent": "ComplianceAgent", "execution_status": "COMPLETED" if step > 7 else ("RUNNING" if step == 7 else "PENDING"), "confidence": 0.90, "execution_time": 0.8},
                {"task_id": "generate_response", "assigned_agent": "ConversationAgent", "execution_status": "COMPLETED" if step > 8 else ("RUNNING" if step == 8 else "PENDING"), "confidence": 0.98, "execution_time": 0.5}
            ]
            
            snapshots.append({
                "step": step,
                "current_status": current_status,
                "overall_confidence": overall_confidence,
                "active_agent": current_active,
                "narrative_timeline": narratives[:step+1],
                "latest_narrative": narratives[step],
                "tasks": tasks,
                "quality_scores": {
                    "Planning": 0.92,
                    "Execution": 0.80 if step < 6 else 0.95,
                    "Evidence": 0.65 if step < 6 else 0.92,
                    "Overall": overall_confidence
                },
                "mcp_discovery_events": [
                    {"agent_name": "CarbonCalculationAgent", "query": "get_supplier_carbon_status", "discovered_tools": ["get_supplier_carbon_status", "compute_regional_grid_intensity"], "timestamp": time.time()}
                ] if step > 1 else [],
                "mcp_selection_decisions": [
                    {"agent_name": "CarbonCalculationAgent", "selected_tool": "get_supplier_carbon_status", "reasoning": "Selected get_supplier_carbon_status because it matches query with 98% reliability.", "timestamp": time.time()}
                ] if step > 2 else [],
                "mcp_tool_chains": [
                    {"agent_name": "CarbonCalculationAgent", "tool_name": "get_supplier_carbon_status", "args": {"supplier_id": 2}, "timestamp": time.time()},
                    {"agent_name": "CarbonCalculationAgent", "tool_name": "compute_regional_grid_intensity", "args": {"country": "FR"}, "timestamp": time.time()}
                ] if step > 4 else [],
                "mcp_fallback_events": [
                    {
                        "agent_name": "CarbonCalculationAgent",
                        "type": "Factor Missing",
                        "supplier_id": 2,
                        "fallback_tool": "compute_regional_grid_intensity",
                        "fallback_value": 0.42
                    }
                ] if step > 5 else [],
                "mcp_validation_events": [
                    {
                        "agent_name": "CarbonCalculationAgent",
                        "tool_name": "compute_regional_grid_intensity",
                        "is_valid": True,
                        "message": "Output matches float intensity model.",
                        "timestamp": time.time()
                    }
                ] if step > 6 else [],
                "goal_model": {
                    "goal_id": "goal_mcp_discovery",
                    "user_intent": "discover emissions calculation tools",
                    "desired_outcome": "Locate and validate emissions calculation tools, utilizing fallback chains if direct metrics are missing.",
                    "success_criteria": ["Emissions calculated", "Validation complete"],
                    "remaining_unknowns": []
                },
                "planning_hypothesis": {
                    "hypotheses": [
                        {"hypothesis_text": "H1: Retrieve historical monthly emissions and run linear regression forecast.", "confidence": 0.95, "selected": True}
                    ],
                    "selected_hypothesis_index": 0,
                    "discarded_hypotheses": []
                },
                "decision_journal": [
                    {"timestamp": "10:00", "decision": "PLAN_INITIALIZED", "reason": "Formulated tool discovery chain.", "evidence": "User Query", "confidence": 1.0, "alternative_considered": [], "expected_outcome": "Find emission factors"}
                ]
            })
            
        execution_runs[run_id]["snapshots"] = snapshots
        execution_runs[run_id]["scorecard"] = {
            "mission_success": "COMPLETED (100%)",
            "overall_confidence": "96%",
            "recovered_issues": "1 (Fallback grid applied)",
            "autonomous_decisions": "1 fallback switch",
            "organizations_contacted": "1 local database",
            "agents_used": "4 agents",
            "mcp_tools_used": "3 tools",
            "negotiations_completed": "0",
            "consensus_score": "98%",
            "reflection_improvements": "N/A (No failure)",
            "execution_time": "3.2s",
            "carbon_saved": "820 tCO2",
            "compliance_risk_reduced": "90% reduction",
            "quality_score": "9.4/10"
        }

    # SCENARIOS 3 & 4 (default fallback)
    else:
        # Default scenario simulation for manifest_upload
        for step in range(10):
            timestamp = f"11:{step:02d}"
            status_map = ["PLANNING", "INGESTING", "CALCULATING", "AUDITING", "OPTIMIZING", "CRITIQUE", "REFLECTION", "RECOVERY", "COMPLETED", "COMPLETED"]
            current_status = status_map[min(step, len(status_map)-1)]
            confidences = [0.85, 0.88, 0.88, 0.85, 0.82, 0.70, 0.65, 0.94, 0.97, 0.97]
            overall_confidence = confidences[step]
            
            narratives = [
                {"time": "11:00", "message": "Planner started objective: calculate emissions for uploaded manifest.", "type": "planner", "explanation": "Planner parses uploaded manifest CSV containing 3 shipments and maps downstream calculation tasks."},
                {"time": "11:01", "message": "Data Ingest Agent parsed manifest and loaded shipments database.", "type": "tool", "explanation": "CSV records validated and written to DB. Triggers carbon calculations."},
                {"time": "11:02", "message": "Carbon Calculation Agent completed emissions run.", "type": "tool", "explanation": "Emissions factors applied. Ingested shipments mapped to standard Scope 3 parameters."},
                {"time": "11:03", "message": "Compliance Agent verified CBAM compliance values.", "type": "consensus", "explanation": "Tariff liabilities calculated based on current EU carbon prices (€80/tonne)."},
                {"time": "11:04", "message": "Optimization Agent suggested carrier alternatives, saving 28% carbon.", "type": "consensus", "explanation": "Logistics carrier swap recommended for route segment CN -> DE, utilizing rail instead of maritime shipping."},
                {"time": "11:05", "message": "Compliance Agent critique raised: Carrier switch is missing safety audits.", "type": "reflection", "explanation": "Compliance flags carrier swap risk due to lack of ISO safety documentation."},
                {"time": "11:06", "message": "Reflection Agent detected audit gap, flagging planning variance.", "type": "reflection", "explanation": "Identifies compliance risk. Suggests query to transport directory for audited carriers."},
                {"time": "11:07", "message": "Transport Agent verified audited rail carriers, resolving compliance warning.", "type": "recovery", "explanation": "Transport verification completed. Safety logs successfully attached. Risk reduced to zero."},
                {"time": "11:08", "message": "Final report generated with verified green stamp and optimizations.", "type": "success", "explanation": "Goal complete. Final summary compiled for user."},
                {"time": "11:09", "message": "Scorecard finalized.", "type": "success", "explanation": "Scorecard completed."}
            ]
            
            active_agents = ["PlannerAgent", "CarbonCalculationAgent", "CarbonCalculationAgent", "ComplianceAgent", "OptimizationAgent", "ComplianceAgent", "ReflectionAgent", "TransportAgent", "ConversationAgent", "ConversationAgent"]
            current_active = active_agents[min(step, len(active_agents)-1)]
            
            tasks = [
                {"task_id": "run_calc", "assigned_agent": "CarbonCalculationAgent", "execution_status": "COMPLETED" if step > 2 else "RUNNING", "confidence": 0.95, "execution_time": 1.1},
                {"task_id": "run_audit", "assigned_agent": "ComplianceAgent", "execution_status": "COMPLETED" if step > 3 else ("RUNNING" if step == 3 else "PENDING"), "confidence": 0.90, "execution_time": 0.7},
                {"task_id": "run_optimize", "assigned_agent": "OptimizationAgent", "execution_status": "COMPLETED" if step > 4 else ("RUNNING" if step == 4 else "PENDING"), "confidence": 0.92, "execution_time": 0.9},
                {"task_id": "generate_response", "assigned_agent": "ConversationAgent", "execution_status": "COMPLETED" if step > 7 else ("RUNNING" if step == 7 else "PENDING"), "confidence": 0.98, "execution_time": 0.5}
            ]
            
            snapshots.append({
                "step": step,
                "current_status": current_status,
                "overall_confidence": overall_confidence,
                "active_agent": current_active,
                "narrative_timeline": narratives[:step+1],
                "latest_narrative": narratives[step],
                "tasks": tasks,
                "quality_scores": {
                    "Planning": 0.95,
                    "Execution": 0.85 if step < 7 else 0.98,
                    "Evidence": 0.70 if step < 7 else 0.95,
                    "Overall": overall_confidence
                },
                "mcp_discovery_events": [
                    {"agent_name": "CarbonCalculationAgent", "query": "compute_emissions_join", "discovered_tools": ["compute_emissions_join"], "timestamp": time.time()}
                ] if step > 1 else [],
                "mcp_selection_decisions": [],
                "reflection_events": [
                    {
                        "stage": "Task",
                        "detected_failure": "Audited Carrier Log Missing",
                        "severity": "MEDIUM",
                        "root_cause": "Optimization carrier alternatives lacked active ISO safety audits in system records.",
                        "confidence_change": {"before": 0.70, "after": 0.94},
                        "recovery_action": "Query TransportAgent for verified registry log.",
                        "summary": "Compliance critique triggered reflection. Transport audit verified alternative carrier."
                    }
                ] if step > 5 else [],
                "goal_model": {
                    "goal_id": "goal_default",
                    "user_intent": "process uploaded manifest",
                    "desired_outcome": "Ingest shipments, calculate Scope 3 footprint, perform compliance audits, and identify green logistic carrier savings.",
                    "success_criteria": ["Shipments calculated", "Optimizations generated", "Audits complete"],
                    "remaining_unknowns": []
                },
                "planning_hypothesis": {
                    "hypotheses": [
                        {"hypothesis_text": "H1: Run sequential calculation cycle, then run audits and optimizations in parallel.", "confidence": 0.95, "selected": True}
                    ],
                    "selected_hypothesis_index": 0,
                    "discarded_hypotheses": []
                },
                "decision_journal": [
                    {"timestamp": "11:00", "decision": "PLAN_INITIALIZED", "reason": "Formulated ingestion and audit DAG.", "evidence": "Manifest Upload", "confidence": 1.0, "alternative_considered": [], "expected_outcome": "Complete manifest process"}
                ]
            })
            
        execution_runs[run_id]["snapshots"] = snapshots
        execution_runs[run_id]["scorecard"] = {
            "mission_success": "COMPLETED (100%)",
            "overall_confidence": "97%",
            "recovered_issues": "1 (Carrier verification)",
            "autonomous_decisions": "2 interventions",
            "organizations_contacted": "2 (Supplier A & DB)",
            "agents_used": "6 agents",
            "mcp_tools_used": "4 tools",
            "negotiations_completed": "0",
            "consensus_score": "96%",
            "reflection_improvements": "+24% confidence",
            "execution_time": "4.1s",
            "carbon_saved": "2,150 tCO2 (28% savings)",
            "compliance_risk_reduced": "95% reduction",
            "quality_score": "9.7/10"
        }
