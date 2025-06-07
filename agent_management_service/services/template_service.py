"""
Servicio para gestión de templates de agentes.
"""

import json
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from agent_management_service.config.settings import get_settings
from agent_management_service.models.template_model import AgentTemplate, TemplateCategory

settings = get_settings()
logger = logging.getLogger(__name__)

class TemplateService:
    """Servicio para gestión de templates."""
    
    def __init__(self):
        """Inicializa el servicio de templates."""
        self.templates_path = Path(settings.templates_path)
        self.system_templates = {}
        self._load_system_templates()
    
    def _load_system_templates(self):
        """Carga templates del sistema desde archivos."""
        system_templates_path = self.templates_path / "system"
        
        # Templates predefinidos si no hay archivos
        default_templates = {
            "customer_service_v1": {
                "id": "customer_service_v1",
                "name": "Customer Service Agent",
                "description": "Agente especializado en atención al cliente",
                "category": "system",
                "minimum_tier": "free",
                "default_config": {
                    "type": "conversational",
                    "model": "llama3-8b-8192",
                    "temperature": 0.3,
                    "system_prompt": "Eres un agente de atención al cliente profesional y empático. Ayudas a resolver dudas y problemas de forma clara y amigable. Siempre mantén un tono profesional pero cercano.",
                    "tools": ["basic_chat", "datetime"],
                    "max_iterations": 3,
                    "max_history_messages": 10
                },
                "use_cases": ["Soporte técnico", "Consultas generales", "Escalamiento"],
                "preview_config": {
                    "example_prompt": "Hola, tengo un problema con mi pedido",
                    "expected_output": "Hola! Lamento escuchar que tienes problemas con tu pedido. Estaré encantado de ayudarte a resolverlo. ¿Podrías proporcionarme tu número de pedido para poder revisarlo?"
                }
            },
            "knowledge_base_v1": {
                "id": "knowledge_base_v1",
                "name": "Knowledge Base Assistant",
                "description": "Agente RAG para consultas en base de conocimiento",
                "category": "system",
                "minimum_tier": "advance",
                "default_config": {
                    "type": "rag",
                    "model": "llama3-8b-8192",
                    "temperature": 0.1,
                    "system_prompt": "Eres un asistente experto que responde basándose en la documentación disponible. Proporciona respuestas precisas y cita las fuentes cuando sea relevante.",
                    "tools": ["rag_query", "rag_search"],
                    "max_iterations": 5,
                    "required_collections_count": 1
                },
                "use_cases": ["FAQ automático", "Documentación técnica", "Manuales"],
                "required_tools": ["rag_query"]
            },
            "sales_assistant_v1": {
                "id": "sales_assistant_v1",
                "name": "Sales Assistant",
                "description": "Agente especializado en ventas y lead qualification",
                "category": "system",
                "minimum_tier": "professional",
                "default_config": {
                    "type": "conversational",
                    "model": "llama3-70b-8192",
                    "temperature": 0.4,
                    "system_prompt": "Eres un experto en ventas que ayuda a calificar leads y proporcionar información sobre productos. Eres persuasivo pero honesto, y siempre buscas entender las necesidades del cliente.",
                    "tools": ["basic_chat", "calculator", "datetime", "external_api"],
                    "max_iterations": 8
                },
                "use_cases": ["Lead qualification", "Product recommendations", "Price calculations"]
            }
        }
        
        # Cargar templates por defecto
        for template_id, template_data in default_templates.items():
            template = AgentTemplate(**template_data)
            self.system_templates[template_id] = template
        
        logger.info(f"Cargados {len(self.system_templates)} templates del sistema")
    
    async def get_template(self, template_id: str, tenant_id: str) -> Optional[AgentTemplate]:
        """Obtiene un template por ID."""
        # Buscar en templates del sistema
        if template_id in self.system_templates:
            return self.system_templates[template_id]
        
        # TODO: Buscar en templates custom del tenant en base de datos
        return None
    
    async def list_templates(
        self,
        tenant_id: str,
        tenant_tier: str,
        category: Optional[str] = None
    ) -> List[AgentTemplate]:
        """Lista templates disponibles para el tenant."""
        templates = []
        
        # Filtrar templates del sistema por tier
        tier_access = settings.tier_limits.get(tenant_tier, {}).get("templates_access", [])
        
        for template in self.system_templates.values():
            # Verificar acceso por tier
            if tier_access == ["all"] or template.id.split("_")[0] in tier_access:
                if not category or template.category == category:
                    templates.append(template)
        
        # TODO: Añadir templates custom del tenant
        
        return templates
    
    async def create_agent_from_template(
        self,
        template_id: str,
        tenant_id: str,
        tenant_tier: str,
        name: str,
        customizations: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Crea configuración de agente desde template."""
        template = await self.get_template(template_id, tenant_id)
        if not template:
            raise ValueError(f"Template {template_id} no encontrado")
        
        # Verificar tier mínimo
        tier_hierarchy = {"free": 0, "advance": 1, "professional": 2, "enterprise": 3}
        if tier_hierarchy.get(tenant_tier, 0) < tier_hierarchy.get(template.minimum_tier, 0):
            raise ValueError(f"Tier {tenant_tier} insuficiente para template {template_id}")
        
        # Crear configuración base desde template
        config = template.default_config.copy()
        config["name"] = name
        config["template_id"] = template_id
        
        # Aplicar customizaciones
        if customizations:
            config.update(customizations)
        
        return config
