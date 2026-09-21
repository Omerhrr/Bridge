"""USSD nodes (hackathon track: USSD-based telecom services).

Africa's Talking USSD protocol:
  - Each callback carries sessionId / serviceCode / phoneNumber / text, where
    `text` is the star-accumulated input (e.g. "1*2").
  - The HTTP response body must start with "CON " (keep the session open) or
    "END " (close the session).

Bridge models a USSD screen as a workflow node:
  - `ussd_menu` renders a menu screen and keeps the session open (CON).
  - `ussd_end`  renders a closing screen and ends the session (END).

The webhook reads the run variables `ussd_response` and `ussd_close` after
execution and builds the CON/END reply.
"""
from typing import Any

from app.modules.workflows.nodes.base import BaseNode, NodeResult, render_template


class UssdMenuNode(BaseNode):
    type = "ussd_menu"
    label = "USSD Menu"
    category = "telecom"
    description = "Shows a USSD menu screen and waits for input (CON)"
    icon = "list"
    config_schema = [
        {"name": "title", "label": "Screen Title", "type": "text", "required": True,
         "hint": "Supports variables like {{phone_number}}"},
        {"name": "options", "label": "Options (one per line)", "type": "textarea",
         "required": False, "hint": "e.g. 1. Check balance"},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        if ctx.resume_input is not None:
            # Resuming after the user answered this menu: continue downstream.
            return NodeResult()
        title = render_template(config.get("title", ""), ctx.variables)
        options = render_template(config.get("options", ""), ctx.variables)
        screen = "\n".join(part for part in (title.strip(), options.strip()) if part)
        ctx.variables["ussd_response"] = screen
        ctx.variables["ussd_close"] = "0"
        await ctx.record("ussd.screen", self, screen=screen, close=False)
        return NodeResult(outputs={"ussd_response": screen}, wait_for_input=True)


class UssdEndNode(BaseNode):
    type = "ussd_end"
    label = "USSD End Screen"
    category = "telecom"
    description = "Shows a final message and closes the USSD session (END)"
    icon = "corner-down-left"
    config_schema = [
        {"name": "message", "label": "Closing Message", "type": "textarea", "required": True,
         "hint": "Supports variables like {{balance_text}}"},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        message = render_template(config.get("message", ""), ctx.variables)
        ctx.variables["ussd_response"] = message
        ctx.variables["ussd_close"] = "1"
        await ctx.record("ussd.screen", self, screen=message, close=True)
        return NodeResult(outputs={"ussd_response": message})
