"""Knowledge Answer node: answer a question from the business knowledge base."""
from typing import Any

from app.modules.workflows.nodes.base import BaseNode, NodeExecutionError, NodeResult, render_template


class KnowledgeAnswerNode(BaseNode):
    type = "knowledge_answer"
    label = "Answer from Knowledge"
    category = "ai"
    description = (
        "Answers the customer's question using only your business knowledge "
        "(website, docs, sheets, database). Unsupported answers are replaced by your fallback message."
    )
    icon = "book-open"
    # One output: the answer (or the fallback message) is always in {{answer}};
    # branch on {{answered}} ("1"/"0") with a Condition node if needed.
    config_schema = [
        {"name": "question", "label": "Question", "type": "textarea", "required": False,
         "hint": "Defaults to the incoming message ({{text}} or {{transcript}})"},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        from app.modules.knowledge.assistant import KnowledgeAssistant
        from app.modules.knowledge.service import log_query

        db = ctx.services.get("db")
        if db is None:
            raise NodeExecutionError("Answer from Knowledge needs a database session")
        question = (
            render_template(config.get("question", ""), ctx.variables)
            or ctx.variables.get("transcript")
            or ctx.variables.get("text", "")
        )
        if not question:
            raise NodeExecutionError("Answer from Knowledge has no question")
        result = await KnowledgeAssistant(db, ctx.services.get("ai")).answer(question)
        phone = ctx.variables.get("sender") or ctx.variables.get("caller") or ctx.variables.get("phone_number")
        await log_query(db, question, result, phone=phone, channel="workflow")
        ctx.variables["answer"] = result.text
        ctx.variables["answered"] = "1" if result.answered else "0"
        await ctx.record("knowledge.answered", self, answered=result.answered, reason=result.reason,
                         sources=[s.source_name for s in result.sources])
        return NodeResult(outputs={"answer": result.text})
