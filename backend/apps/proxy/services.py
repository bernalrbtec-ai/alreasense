"""
Serviço de rotação de proxies Webshare nas instâncias Evolution API.
Migração do proxy_manager.py para Django.
"""
import logging
import random
import secrets
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import ProxyRotationInstanceLog, ProxyRotationLog

logger = logging.getLogger(__name__)


class WebshareProxyManager:
    """Gerenciador de proxies do Webshare.io."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://proxy.webshare.io/api/v2"
        self.headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        }

    def get_proxies(self, limit: int = 100) -> List[Dict]:
        """Busca lista de proxies disponíveis no Webshare.io."""
        try:
            url = f"{self.base_url}/proxy/list/"
            params = {"mode": "direct", "page": 1, "page_size": limit}
            response = requests.get(
                url, headers=self.headers, params=params, timeout=30
            )
            response.raise_for_status()
            data = response.json()
            proxies = data.get("results", [])
            logger.info(f"✓ {len(proxies)} proxies obtidos do Webshare.io")
            return proxies
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Erro ao buscar proxies: {e}")
            return []


class EvolutionAPIManager:
    """Gerenciador de instâncias do Evolution API."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "apikey": api_key,
            "Content-Type": "application/json",
        }

    def list_instances(self) -> List[Dict]:
        """Lista todas as instâncias disponíveis."""
        try:
            url = f"{self.base_url}/instance/fetchInstances"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            instances = response.json()
            logger.info(f"✓ {len(instances)} instâncias encontradas")
            return instances
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Erro ao listar instâncias: {e}")
            return []

    def update_proxy(self, instance_name: str, proxy_data: Dict) -> bool:
        """Atualiza o proxy de uma instância específica."""
        try:
            url = f"{self.base_url}/proxy/set/{instance_name}"
            payload = {
                "enabled": True,
                "host": proxy_data.get("proxy_address", ""),
                "port": str(proxy_data.get("port", 80)),
                "protocol": "http",
                "username": proxy_data.get("username", ""),
                "password": proxy_data.get("password", ""),
            }
            response = requests.post(
                url, headers=self.headers, json=payload, timeout=30
            )
            if response.status_code == 400:
                logger.error(f"✗ Erro 400 ao atualizar proxy: {response.text}")
            response.raise_for_status()
            logger.info(f"✓ Proxy atualizado para instância '{instance_name}'")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Erro ao atualizar proxy de '{instance_name}': {e}")
            return False

    def restart_instance(self, instance_name: str) -> bool:
        """Reinicia uma instância para aplicar as mudanças."""
        try:
            url = f"{self.base_url}/instance/restart/{instance_name}"
            response = requests.post(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            logger.info(f"✓ Instância '{instance_name}' reiniciada")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Erro ao reiniciar instância '{instance_name}': {e}")
            return False

    def send_notification(
        self, instance_name: str, phone_number: str, message: str
    ) -> bool:
        """Envia notificação via WhatsApp usando a Evolution API."""
        try:
            url = f"{self.base_url}/message/sendText/{instance_name}"
            payload = {"number": phone_number, "text": message}
            response = requests.post(
                url, headers=self.headers, json=payload, timeout=30
            )
            response.raise_for_status()
            logger.info(f"✓ Notificação enviada para {phone_number}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Erro ao enviar notificação: {e}")
            return False


def _extract_instance_name(instance) -> Optional[str]:
    """Extrai o nome da instância de diferentes formatos da Evolution API."""
    if isinstance(instance, dict) and "name" in instance:
        return instance.get("name", "").strip() or None
    if isinstance(instance, dict) and "instance" in instance:
        name = instance.get("instance", {}).get("instanceName", "").strip()
        return name or None
    if isinstance(instance, dict) and "instanceName" in instance:
        return instance.get("instanceName", "").strip() or None
    if isinstance(instance, str):
        return instance.strip() or None
    return None


def distribute_proxies(
    instances: List[Dict], proxies: List[Dict], strategy: str = "rotate"
) -> Dict[str, Dict]:
    """Distribui proxies entre as instâncias."""
    distribution = {}
    if not proxies:
        return distribution

    num_proxies = len(proxies)

    for i, instance in enumerate(instances):
        instance_name = _extract_instance_name(instance)
        if not instance_name:
            continue

        if strategy == "rotate":
            proxy_index = i % num_proxies
            distribution[instance_name] = proxies[proxy_index]
        elif strategy == "prioritize":
            if i < num_proxies:
                distribution[instance_name] = proxies[i]
            # else: instância fica sem proxy
        elif strategy == "random":
            distribution[instance_name] = random.choice(proxies)

    return distribution


def _format_notification_message(
    success_count: int,
    total_count: int,
    num_proxies: int,
    num_instances: int,
    strategy: str,
    errors: Optional[List[str]] = None,
) -> str:
    """Formata mensagem de notificação sobre a atualização."""
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    if success_count == total_count:
        status_text = "SUCESSO"
    elif success_count > 0:
        status_text = "PARCIAL"
    else:
        status_text = "FALHOU"

    message = f"""🔄 *ATUALIZAÇÃO DE PROXIES*

📅 *Data/Hora:* {timestamp}
🎯 *Status:* {status_text}

📊 *Resumo:*
• Proxies disponíveis: {num_proxies}
• Instâncias totais: {num_instances}
• Atualizadas: {success_count}/{total_count}
• Estratégia: {strategy}
"""
    if errors:
        message += f"\n❌ *Erros ({len(errors)}):*\n"
        for err in errors[:3]:
            message += f"• {err}\n"
    return message


def run_proxy_rotation(
    triggered_by: str = "manual", user=None
) -> Tuple[Optional[ProxyRotationLog], Optional[str]]:
    """
    Executa a rotação de proxies.
    Retorna (log, error_message). Se sucesso, error_message é None.
    """
    # Lock: verificar se há rotação em andamento
    if ProxyRotationLog.objects.filter(status="running").exists():
        return None, "Já existe uma rotação em execução. Aguarde ou tente novamente mais tarde."

    evolution_url = getattr(settings, "EVOLUTION_API_URL", "") or getattr(
        settings, "EVO_BASE_URL", ""
    )
    evolution_key = getattr(settings, "EVOLUTION_API_KEY", "") or getattr(
        settings, "EVO_API_KEY", ""
    )
    webshare_key = getattr(settings, "WEBSHARE_API_KEY", "")
    proxy_limit = getattr(settings, "WEBSHARE_PROXY_LIMIT", 100)
    strategy = getattr(settings, "PROXY_ROTATION_STRATEGY", "rotate")
    restart_instances = getattr(settings, "PROXY_ROTATION_RESTART_INSTANCES", True)
    wait_after_update = getattr(
        settings, "PROXY_ROTATION_WAIT_AFTER_UPDATE_SECONDS", 2
    )
    wait_between = getattr(settings, "PROXY_ROTATION_WAIT_SECONDS", 3)
    notifications_enabled = getattr(settings, "PROXY_NOTIFICATION_ENABLED", False)
    notification_instance = getattr(settings, "PROXY_NOTIFICATION_INSTANCE", "")
    notification_phone = getattr(settings, "PROXY_NOTIFICATION_PHONE", "")

    if not webshare_key or not evolution_url or not evolution_key:
        return None, "Credenciais não configuradas (WEBSHARE_API_KEY, EVOLUTION_API_URL, EVOLUTION_API_KEY)."

    # Criar log
    log = ProxyRotationLog.objects.create(
        status="running",
        triggered_by=triggered_by,
        strategy=strategy,
        created_by=user,
    )

    errors: List[str] = []
    success_count = 0

    try:
        webshare = WebshareProxyManager(webshare_key)
        evolution = EvolutionAPIManager(evolution_url, evolution_key)

        proxies = webshare.get_proxies(limit=proxy_limit)
        if not proxies:
            log.status = "failed"
            log.error_message = "Nenhum proxy disponível no Webshare"
            log.finished_at = timezone.now()
            log.num_proxies = 0
            log.num_instances = 0
            log.num_updated = 0
            log.save()
            return log, "Nenhum proxy disponível no Webshare."

        instances = evolution.list_instances()
        if not instances:
            log.status = "failed"
            log.error_message = "Nenhuma instância encontrada na Evolution API"
            log.finished_at = timezone.now()
            log.num_proxies = len(proxies)
            log.num_instances = 0
            log.num_updated = 0
            log.save()
            return log, "Nenhuma instância encontrada na Evolution API."

        distribution = distribute_proxies(instances, proxies, strategy)
        log.num_proxies = len(proxies)
        log.num_instances = len(instances)
        log.save()

        for instance_name, proxy_data in distribution.items():
            if not instance_name:
                continue

            success = False
            err_msg = None

            if evolution.update_proxy(instance_name, proxy_data):
                time.sleep(wait_after_update)
                if restart_instances:
                    if evolution.restart_instance(instance_name):
                        success = True
                        success_count += 1
                    else:
                        err_msg = f"Falha ao reiniciar {instance_name}"
                        errors.append(err_msg)
                else:
                    success = True
                    success_count += 1
                time.sleep(wait_between)
            else:
                err_msg = f"Falha ao atualizar proxy de {instance_name}"
                errors.append(err_msg)

            ProxyRotationInstanceLog.objects.create(
                rotation_log=log,
                instance_name=instance_name,
                proxy_host=proxy_data.get("proxy_address", ""),
                proxy_port=proxy_data.get("port", 80),
                success=success,
                error_message=err_msg,
            )

        # Atualizar log final
        log.num_updated = success_count
        log.finished_at = timezone.now()
        if success_count == len(distribution):
            log.status = "success"
            log.error_message = None
        elif success_count > 0:
            log.status = "partial"
            log.error_message = "; ".join(errors[:5]) if errors else None
        else:
            log.status = "failed"
            log.error_message = "; ".join(errors[:5]) if errors else "Nenhuma instância atualizada"
        log.save()

        # Notificação WhatsApp
        if notifications_enabled and notification_instance and notification_phone:
            msg = _format_notification_message(
                success_count, len(distribution), len(proxies), len(instances),
                strategy, errors if errors else None,
            )
            try:
                evolution.send_notification(
                    notification_instance, notification_phone, msg
                )
            except Exception as e:
                logger.warning(f"Falha ao enviar notificação WhatsApp: {e}")

        return log, None

    except Exception as e:
        logger.exception(f"Erro inesperado na rotação de proxies: {e}")
        log.status = "failed"
        log.error_message = str(e)
        log.finished_at = timezone.now()
        log.save()
        return log, str(e)


def _validate_proxy_api_key(request) -> Tuple[bool, Optional[str]]:
    """Valida API key do header X-API-Key ou Authorization Bearer."""
    configured = getattr(settings, "PROXY_ROTATION_API_KEY", "") or ""
    if not configured:
        return False, "Endpoint desabilitado (PROXY_ROTATION_API_KEY não configurada)"
    provided = (
        request.headers.get("X-API-Key")
        or (request.headers.get("Authorization") or "").replace("Bearer ", "").strip()
    )
    if not provided:
        return False, "API key ausente"
    if not secrets.compare_digest(configured, provided):
        return False, "API key inválida"
    return True, None
