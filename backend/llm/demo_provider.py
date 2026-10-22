"""Demo Mock Provider — strictly permitted ONLY when DEMO_MODE=true."""

import logging
from typing import Optional, Dict, Any
from backend.llm.base import BaseLLMProvider

logger = logging.getLogger("lecturenotes.llm.demo")


class DemoProvider(BaseLLMProvider):
    """Generates synthetic structured lecture data for testing without live APIs.
    
    NOTE: Every output produced by this provider is flagged as DEMO_DATA and must
    carry a visible watermark and cover label in the generated PDF.
    """

    def __init__(self, model_name: str = "demo-mock-engine"):
        super().__init__(model_name=model_name)
        self.is_demo = True

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return "[DEMO DATA] Synthesized lecture notes summary for demonstration purposes."

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Return structured demo content with clear demo markers."""
        logger.info("[DEMO_MODE] Generating synthetic lecture notes and questions")
        return {
            "title": "[DEMO DATA] Classical Mechanics & Thermodynamics",
            "subject": "Physics & Engineering",
            "summary": "This is a demonstration study book generated in DEMO_MODE. All formulas, numericals, and questions are synthetic examples designed to showcase the PDF layout and KaTeX rendering.",
            "formula_sheet": [
                {"name": "Newton's Second Law", "latex": r"F = m \cdot a", "description": "Relates net force, mass, and acceleration"},
                {"name": "Kinetic Energy", "latex": r"E_k = \frac{1}{2} m v^2", "description": "Translational kinetic energy of a moving body"},
                {"name": "Ideal Gas Law", "latex": r"P V = n R T", "description": "Equation of state for a hypothetical ideal gas"},
                {"name": "First Law of Thermodynamics", "latex": r"\Delta U = Q - W", "description": "Conservation of energy in thermodynamic systems"}
            ],
            "sections": [
                {
                    "id": "sec-1",
                    "title": "Fundamental Laws of Motion",
                    "concepts": [
                        {
                            "name": "Inertia and Force",
                            "explanation": "An object at rest stays at rest, and an object in motion continues with constant velocity unless acted upon by a net external force.",
                            "key_points": [
                                "Inertia is directly proportional to mass ($m$).",
                                "Force is a vector quantity measured in Newtons ($N$).",
                                "Momentum is defined as $p = m \\cdot v$."
                            ],
                            "latex": r"\vec{F}_{net} = \frac{d\vec{p}}{dt} = m \vec{a}"
                        }
                    ],
                    "callouts": [
                        {
                            "type": "tip",
                            "title": "Exam Tip",
                            "text": "Always draw a Free Body Diagram (FBD) before setting up equations of motion."
                        }
                    ]
                },
                {
                    "id": "sec-2",
                    "title": "Thermodynamic Work and Heat Transfer",
                    "concepts": [
                        {
                            "name": "Isobaric Expansion",
                            "explanation": "In a constant pressure process, work done by the gas is equal to pressure multiplied by the volume change.",
                            "key_points": [
                                "Isobaric means $\\Delta P = 0$.",
                                "Work done: $W = P \\Delta V = P (V_2 - V_1)$."
                            ],
                            "latex": r"W = \int_{V_1}^{V_2} P \, dV = P(V_2 - V_1)"
                        }
                    ]
                }
            ],
            "numericals": [
                {
                    "id": "num-1",
                    "title": "Kinetic Energy of an Accelerated Vehicle",
                    "problem": "A vehicle with mass $m = 1200\\text{ kg}$ accelerates uniformly from rest to a speed of $v = 25\\text{ m/s}$. Calculate the net work done on the vehicle and its final kinetic energy.",
                    "given": {
                        "Mass (m)": "1200 kg",
                        "Initial velocity (v_0)": "0 m/s",
                        "Final velocity (v)": "25 m/s"
                    },
                    "find": "Final Kinetic Energy (E_k) and Net Work Done (W_net)",
                    "formulas_used": [
                        r"E_k = \frac{1}{2} m v^2",
                        r"W_{net} = \Delta E_k = E_{k,f} - E_{k,i}"
                    ],
                    "steps": [
                        {"step_number": 1, "description": "Substitute mass and final velocity into the kinetic energy equation", "latex": r"E_k = \frac{1}{2} (1200) (25)^2 = 600 \times 625"},
                        {"step_number": 2, "description": "Compute the numerical product", "latex": r"E_k = 375,000 \text{ J} = 375 \text{ kJ}"},
                        {"step_number": 3, "description": "Apply Work-Energy Theorem: since initial kinetic energy is zero, net work done equals final kinetic energy", "latex": r"W_{net} = 375 \text{ kJ}"}
                    ],
                    "final_answer": "Final Kinetic Energy = 375 kJ; Net Work Done = 375 kJ",
                    "tips": "Notice that doubling the speed quadruples the kinetic energy due to the $v^2$ term."
                }
            ],
            "questions": [
                {
                    "id": "q-1",
                    "difficulty": "Easy",
                    "category": "Theory",
                    "question": "State Newton's First Law of Motion and define the physical meaning of inertia.",
                    "options": [],
                    "answer": "Newton's First Law states that every object will remain at rest or in uniform motion in a straight line unless compelled to change its state by the action of an external force. Inertia is the inherent property of matter by which it continues in its existing state of rest or uniform motion.",
                    "explanation": "Mass is the quantitative measure of inertia."
                },
                {
                    "id": "q-2",
                    "difficulty": "Moderate",
                    "category": "Numerical",
                    "question": "A gas expands from $0.02\\text{ m}^3$ to $0.05\\text{ m}^3$ under a constant pressure of $2.0 \\times 10^5\\text{ Pa}$. Calculate the work done by the gas.",
                    "options": [],
                    "answer": "6,000 J (6 kJ)",
                    "explanation": r"$W = P \Delta V = 2.0 \times 10^5 \times (0.05 - 0.02) = 2.0 \times 10^5 \times 0.03 = 6000\text{ J}$."
                },
                {
                    "id": "q-3",
                    "difficulty": "Hard",
                    "category": "Theory",
                    "question": "Explain why the efficiency of a Carnot heat engine cannot exceed $1 - \frac{T_C}{T_H}$, and discuss its implications for the Second Law of Thermodynamics.",
                    "options": [],
                    "answer": "Carnot's theorem proves that no engine operating between two heat reservoirs can be more efficient than a reversible Carnot engine. This stems directly from the Kelvin-Planck and Clausius statements of the Second Law: 100% conversion of heat into cyclic work without entropy generation is physically impossible.",
                    "explanation": "Absolute temperature $T_C > 0$ ensures efficiency is always strictly less than 1."
                }
            ]
        }

    async def check_connection(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "provider": "demo",
            "model": self.model_name,
            "latency_ms": 1,
            "note": "Demo mode active. Generates watermarked synthetic study books.",
        }
