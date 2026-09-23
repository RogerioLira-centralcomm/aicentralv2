"""Schemas for explicit, portable MCP application contexts."""

from ..registry import register_tool


_HANDLE = {"type": "string", "minLength": 20, "maxLength": 180}


def _placeholder(_context, _arguments):
    raise RuntimeError("Context tools are executed by the MCP context runtime.")


register_tool(name="context.open", description="Abre um contexto Cadu persistente e retorna context_handle para reutilizar nas próximas ferramentas.",
              capability="workspace", exposures=("internal", "customer_agent"), input_schema={"type":"object","properties":{
                  "conversation_id":{"type":["string","null"],"maxLength":80}, "project_ref":{"type":["string","null"],"maxLength":160},
                  "brand_ref":{"type":["string","null"],"maxLength":160}, "label":{"type":"string","maxLength":120}},"additionalProperties":False})(_placeholder)
register_tool(name="context.get", description="Retoma o estado e as operações recentes de um contexto Cadu.", capability="workspace",
              exposures=("internal","customer_agent"), input_schema={"type":"object","required":["context_handle"],
              "properties":{"context_handle":_HANDLE},"additionalProperties":False})(_placeholder)
register_tool(name="context.update", description="Altera explicitamente projeto, marca ou objeto ativo do contexto Cadu.", capability="workspace", effect="write",
              exposures=("internal","customer_agent"), input_schema={"type":"object","required":["context_handle"],"properties":{
                  "context_handle":_HANDLE,"project_ref":{"type":["string","null"],"maxLength":160},"brand_ref":{"type":["string","null"],"maxLength":160},
                  "active_object":{"type":["object","null"],"properties":{"type":{"type":"string","maxLength":80},"id":{"type":"string","maxLength":180}},
                                   "required":["type","id"],"additionalProperties":False},
                  "label":{"type":"string","maxLength":120}},"additionalProperties":False})(_placeholder)
register_tool(name="context.close", description="Encerra o contexto MCP sem apagar conversas ou artefatos do Cadu.", capability="workspace", effect="write",
              exposures=("internal","customer_agent"), input_schema={"type":"object","required":["context_handle"],
              "properties":{"context_handle":_HANDLE},"additionalProperties":False})(_placeholder)
