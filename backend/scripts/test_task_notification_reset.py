#!/usr/bin/env python
"""
Script para testar se o reset de notification_sent funciona ao atualizar um agendamento
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from apps.contacts.models import Task
from apps.authn.models import User
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_notification_reset():
    """Testa se notification_sent é resetado ao atualizar due_date"""
    print("\n" + "="*60)
    print("🧪 TESTE: Reset de notification_sent ao atualizar agendamento")
    print("="*60)
    
    # Buscar uma tarefa de agenda para testar
    user_email = os.environ.get('USER_EMAIL', 'paulo.bernal@rbtec.com.br')
    try:
        user = User.objects.get(email=user_email)
        print(f"✅ Usuário encontrado: {user.email}")
        
        # Buscar uma tarefa de agenda do usuário
        task = Task.objects.filter(
            assigned_to=user,
            tenant=user.tenant,
            task_type='agenda',
            status__in=['pending', 'in_progress']
        ).first()
        
        if not task:
            print("❌ Nenhuma tarefa de agenda encontrada para testar")
            print("   Criando uma tarefa de teste...")
            
            from apps.authn.models import Department
            department = Department.objects.filter(tenant=user.tenant).first()
            
            task = Task.objects.create(
                title="Teste de Notificação",
                description="Tarefa criada para testar reset de notification_sent",
                tenant=user.tenant,
                created_by=user,
                assigned_to=user,
                department=department,
                task_type='agenda',
                due_date=timezone.now() + timedelta(hours=1),
                status='pending',
                notification_sent=True  # Marcar como já notificada
            )
            print(f"✅ Tarefa de teste criada: {task.id}")
        
        print(f"\n📋 Tarefa encontrada:")
        print(f"   ID: {task.id}")
        print(f"   Título: {task.title}")
        print(f"   Due Date: {task.due_date}")
        print(f"   Notification Sent (ANTES): {task.notification_sent}")
        
        # Atualizar due_date
        new_due_date = task.due_date + timedelta(hours=2)
        print(f"\n🔄 Atualizando due_date de {task.due_date} para {new_due_date}")
        
        # Usar o serializer para simular a atualização via API
        from apps.contacts.serializers import TaskCreateSerializer
        from rest_framework.test import APIRequestFactory
        from rest_framework.request import Request
        
        factory = APIRequestFactory()
        request = factory.put(f'/api/contacts/tasks/{task.id}/')
        request.user = user
        drf_request = Request(request)
        
        serializer = TaskCreateSerializer(
            instance=task,
            data={'due_date': new_due_date},
            context={'request': drf_request},
            partial=True
        )
        
        if serializer.is_valid():
            updated_task = serializer.save()
            print(f"\n✅ Tarefa atualizada com sucesso!")
            print(f"   Due Date (DEPOIS): {updated_task.due_date}")
            print(f"   Notification Sent (DEPOIS): {updated_task.notification_sent}")
            
            if updated_task.notification_sent == False:
                print("\n✅ SUCESSO: notification_sent foi resetado para False!")
                return True
            else:
                print("\n❌ FALHA: notification_sent NÃO foi resetado!")
                return False
        else:
            print(f"\n❌ Erro de validação: {serializer.errors}")
            return False
            
    except User.DoesNotExist:
        print(f"❌ Usuário não encontrado: {user_email}")
        return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_notification_reset()
    sys.exit(0 if success else 1)

