from pymongo import MongoClient
from django.conf import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MongoDBClient:
    def __init__(self):
        self.client = None
        self.db = None
        self.collection = None
        
    def connect(self):
        """Conecta ao MongoDB"""
        try:
            self.client = MongoClient(settings.MONGO_URL)
            self.db = self.client[settings.MONGO_CONFIG['DATABASE']]
            self.collection = self.db[settings.MONGO_CONFIG['COLLECTION']]
            
            # Criar índices para performance
            self.collection.create_index([("status", 1)])
            self.collection.create_index([("created_at", 1)])
            self.collection.create_index([("whatsapp_message_id", 1)])
            
            logger.info("✅ [MONGO] Conectado com sucesso")
            return True
        except Exception as e:
            logger.error(f"❌ [MONGO] Erro na conexão: {e}")
            return False
    
    def insert_webhook_event(self, event_data):
        """Insere um evento de webhook"""
        try:
            # Adicionar timestamp se não existir
            if 'created_at' not in event_data:
                event_data['created_at'] = datetime.utcnow()
            
            result = self.collection.insert_one(event_data)
            logger.info(f"✅ [MONGO] Evento inserido: {result.inserted_id}")
            return result.inserted_id
        except Exception as e:
            logger.error(f"❌ [MONGO] Erro ao inserir evento: {e}")
            return None
    
    def get_pending_events(self, limit=100):
        """Busca eventos pendentes"""
        try:
            events = list(self.collection.find(
                {"status": "pending"}
            ).sort("created_at", 1).limit(limit))
            logger.info(f"✅ [MONGO] {len(events)} eventos pendentes encontrados")
            return events
        except Exception as e:
            logger.error(f"❌ [MONGO] Erro ao buscar eventos: {e}")
            return []
    
    def mark_as_processed(self, event_id):
        """Marca evento como processado"""
        try:
            result = self.collection.update_one(
                {"_id": event_id},
                {"$set": {"status": "processed", "processed_at": datetime.utcnow()}}
            )
            logger.info(f"✅ [MONGO] Evento {event_id} marcado como processado")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ [MONGO] Erro ao marcar como processado: {e}")
            return False
    
    def mark_as_error(self, event_id, error_message):
        """Marca evento como erro"""
        try:
            result = self.collection.update_one(
                {"_id": event_id},
                {
                    "$set": {
                        "status": "error", 
                        "error_message": error_message,
                        "processed_at": datetime.utcnow()
                    }
                }
            )
            logger.info(f"✅ [MONGO] Evento {event_id} marcado como erro")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ [MONGO] Erro ao marcar como erro: {e}")
            return False
    
    def increment_retry_count(self, event_id):
        """Incrementa contador de retry"""
        try:
            result = self.collection.update_one(
                {"_id": event_id},
                {"$inc": {"retry_count": 1}}
            )
            logger.info(f"✅ [MONGO] Contador de retry incrementado para evento {event_id}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ [MONGO] Erro ao incrementar retry: {e}")
            return False
    
    def get_event_stats(self):
        """Retorna estatísticas dos eventos"""
        try:
            stats = {
                'total': self.collection.count_documents({}),
                'pending': self.collection.count_documents({"status": "pending"}),
                'processed': self.collection.count_documents({"status": "processed"}),
                'error': self.collection.count_documents({"status": "error"})
            }
            logger.info(f"✅ [MONGO] Estatísticas: {stats}")
            return stats
        except Exception as e:
            logger.error(f"❌ [MONGO] Erro ao buscar estatísticas: {e}")
            return {}

# Instância global
mongodb_client = MongoDBClient()
