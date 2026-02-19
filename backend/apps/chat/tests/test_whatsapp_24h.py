"""
Testes Fase 6: janela 24h e cenário de race (webhook atrasado, resposta antes do commit).

Cenários:
1) Janela 24h: apenas mensagens inbound renovam; sem inbound = fora da janela.
2) Com inbound recente = dentro da janela (texto livre permitido).
3) Race: garantir que a decisão "dentro da janela" usa leitura consistente do banco
   (Message persistida antes de notificar; ao processar resposta do agente, a inbound já está commitada).
"""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from apps.chat.models import Conversation, Message
from apps.chat.whatsapp_24h import get_last_inbound_at, is_within_24h_window
from apps.tenancy.models import Tenant


class WhatsApp24hWindowTests(TestCase):
    """Testes da janela de 24h (apenas inbound do contato)."""

    def setUp(self):
        self.tenant = Tenant.objects.filter().first()
        if not self.tenant:
            self.tenant = Tenant.objects.create(name="Test Tenant")
        self.conversation = Conversation.objects.create(
            tenant=self.tenant,
            contact_phone="+5511999999999",
            contact_name="Test Contact",
            instance_name="test_instance",
            conversation_type="individual",
        )

    def test_no_inbound_outside_window(self):
        """Sem nenhuma mensagem inbound, conversa está fora da janela."""
        self.assertFalse(is_within_24h_window(self.conversation))
        self.assertIsNone(get_last_inbound_at(self.conversation))

    def test_outbound_does_not_open_window(self):
        """Mensagem outbound (nossa) NÃO abre/renova a janela."""
        Message.objects.create(
            conversation=self.conversation,
            content="Olá, somos nós",
            direction="outgoing",
            status="sent",
        )
        self.assertFalse(is_within_24h_window(self.conversation))
        self.assertIsNone(get_last_inbound_at(self.conversation))

    def test_inbound_recent_within_window(self):
        """Mensagem inbound recente coloca a conversa dentro da janela."""
        Message.objects.create(
            conversation=self.conversation,
            content="Oi",
            direction="incoming",
            status="sent",
            sender_phone="5511999999999",
        )
        self.assertTrue(is_within_24h_window(self.conversation))
        last = get_last_inbound_at(self.conversation)
        self.assertIsNotNone(last)

    def test_inbound_old_outside_window(self):
        """Mensagem inbound com mais de 24h coloca a conversa fora da janela."""
        old = timezone.now() - timedelta(hours=25)
        msg = Message.objects.create(
            conversation=self.conversation,
            content="Oi",
            direction="incoming",
            status="sent",
            sender_phone="5511999999999",
        )
        Message.objects.filter(pk=msg.pk).update(created_at=old)
        self.conversation.refresh_from_db()
        # recarregar last_inbound
        self.assertFalse(is_within_24h_window(self.conversation))

    def test_race_persist_before_broadcast(self):
        """
        Cenário de race: decisão 'dentro da janela' deve usar leitura consistente do banco.
        Simulação: criar inbound (commit); em seguida a verificação 24h deve ver a mensagem.
        Assim, quando o webhook persiste a Message antes de notificar (on_commit broadcast),
        qualquer resposta do agente processada depois verá a inbound e não forçará template.
        """
        Message.objects.create(
            conversation=self.conversation,
            content="Mensagem do contato",
            direction="incoming",
            status="sent",
            sender_phone="5511999999999",
        )
        # Leitura após "commit" (em outro fluxo seria outra transação)
        self.assertTrue(
            is_within_24h_window(self.conversation),
            "Após persistir inbound, conversa deve estar dentro da janela",
        )
