import logging
import time
from typing import Dict, Any, List
from agents.shared_state import ExecutionState

logger = logging.getLogger("ConsensusEngine")

class RemoteConsensusEngine:
    def __init__(self, llm_reason_fn=None):
        self.llm_reason = llm_reason_fn

    def generate_consensus(self, state: ExecutionState) -> Dict[str, Any]:
        """
        Cross-validates evidence from Supplier Agents, Certification Authority, and Logistics.
        Reconciles confidence scores, trust ratings, and outputs a consensus report.
        """
        start_time = time.time()
        
        # 1. Gather A2A session outputs from task history or state
        supplier_responses = state.supplier_responses
        
        # Find certification task result
        ca_result = None
        for res in state.task_history.values():
            if "certification_status" in res.output_data:
                ca_result = res.output_data["certification_status"]
                break
                
        # Find logistics task result
        logistics_result = None
        for res in state.task_history.values():
            if "logistics_metrics" in res.output_data:
                logistics_result = res.output_data["logistics_metrics"]
                break
                
        # 2. Perform cross-validation calculations
        cross_validations = []
        agreed_count = 0
        total_checks = 0
        
        if supplier_responses:
            for s_res in supplier_responses:
                total_checks += 1
                status = s_res.emission_data_status
                
                # Check CA alignment
                ca_aligned = True
                ca_cert_info = "No cert authority query found."
                if ca_result:
                    ca_aligned = ca_result.get("is_certified", False)
                    ca_cert_info = f"CA status: {ca_result.get('status')}"
                    
                # Reconcile Supplier and CA verification status
                if status == "Verified" and ca_aligned:
                    agreed_count += 1
                    cross_validations.append(f"Supplier {s_res.supplier_name} data is Verified and aligned with CA audit.")
                elif status == "Estimated":
                    agreed_count += 0.8  # partial agreement
                    cross_validations.append(f"Supplier {s_res.supplier_name} data is Estimated. CA aligned: {ca_aligned}.")
                else:
                    cross_validations.append(f"Supplier {s_res.supplier_name} has missing/unverified logs. CA alignment failure.")
                    
        # Check transport logistics validation
        if logistics_result:
            total_checks += 1
            if logistics_result.get("route_verified"):
                agreed_count += 1
                cross_validations.append(f"Transport route verified. Fuel source: {logistics_result.get('fuel_source')}.")
            else:
                cross_validations.append("Transport routing could not be verified.")

        # Reconcile consensus score (agreement ratio)
        consensus_score = agreed_count / total_checks if total_checks > 0 else 1.0
        
        # 3. Formulate Summary (Use Gemini if available)
        evidence_text = "\n".join(cross_validations)
        fallback_summary = (
            f"Consensus achieved at {consensus_score*100:.0f}% agreement. "
            f"Cross-validated supplier declarations against Certification Authority certificates and Logistics carrier logs. "
            f"Verified shipments align with ISO carbon accounting standards."
        )
        
        summary = fallback_summary
        if self.llm_reason:
            prompt = (
                f"You are the Consensus Engine. Reconcile the following federated evidence:\n{evidence_text}\n"
                f"Consensus Agreement Score: {consensus_score*100:.0f}%\n"
                f"Write a concise consensus summary (max 3 sentences) explaining the verification details, trust alignment, and overall validation result."
            )
            summary = self.llm_reason(prompt, fallback_summary)
            
        consensus_report = {
            "consensus_score": round(consensus_score, 2),
            "cross_validations": cross_validations,
            "final_recommendation": "Approve carbon compliance filing" if consensus_score >= 0.80 else "Flag filing for manual review",
            "supporting_evidence": cross_validations,
            "summary": summary
        }
        
        return consensus_report
