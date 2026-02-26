"""
Services para importação e exportação de contatos
"""

import csv
import io
import logging
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.utils import timezone
from django.db import transaction
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Contact, ContactImport, Tag
from .utils import normalize_phone, get_state_from_ddd, extract_ddd_from_phone, get_state_from_phone

logger = logging.getLogger(__name__)


# Mapeamento de aliases de colunas
FIELD_ALIASES = {
    'phone': ['telefone', 'celular', 'whatsapp', 'fone', 'tel'],
    'name': ['nome', 'cliente', 'contato'],
    'email': ['e-mail', 'mail'],
    'birth_date': ['data_nascimento', 'nascimento', 'aniversario', 'birthday'],
    'city': ['cidade', 'municipio'],
    'state': ['estado', 'uf'],
    'zipcode': ['cep', 'zip', 'postal_code'],
    'notes': ['observacoes', 'obs', 'comentarios', 'anotacoes'],
    'tags': ['etiquetas', 'categorias', 'grupos'],
    'last_purchase_date': ['data_compra', 'ultima_compra'],
    'last_purchase_value': ['valor_compra', 'valor'],
}

VALID_STATES = [
    'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA',
    'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN',
    'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'
]


class ContactImportService:
    """Service para importação de contatos via CSV"""
    
    def __init__(self, tenant, user):
        self.tenant = tenant
        self.user = user
    
    def _decode_file_content(self, raw_content):
        """
        Tenta decodificar o arquivo com múltiplos encodings
        
        Args:
            raw_content: Conteúdo bruto do arquivo
            
        Returns:
            str: Conteúdo decodificado
        """
        encodings = ['utf-8-sig', 'utf-8', 'cp1252', 'iso-8859-1', 'latin1']
        
        for encoding in encodings:
            try:
                return raw_content.decode(encoding)
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        # Se nenhum encoding funcionar, usar utf-8 com errors='replace'
        return raw_content.decode('utf-8', errors='replace')
    
    def preview_csv(self, file, max_rows=10):
        """
        Gera preview do CSV para o usuário revisar antes de importar
        
        Args:
            file: Arquivo CSV
            max_rows: Número máximo de linhas para preview
            
        Returns:
            dict: Preview com headers, mapeamento, samples
        """
        try:
            # Ler CSV com detecção automática de encoding
            raw_content = file.read()
            decoded_file = self._decode_file_content(raw_content)
            file.seek(0)  # Reset para poder ler novamente depois
            
            # Auto-detectar delimitador (vírgula ou ponto-e-vírgula)
            delimiter = self._detect_delimiter(decoded_file)
            
            csv_reader = csv.DictReader(io.StringIO(decoded_file), delimiter=delimiter)
            headers = csv_reader.fieldnames
            
            # Mapear colunas automaticamente
            column_mapping = self._auto_map_columns(headers)
            
            # Pegar primeiras linhas como sample
            rows = []
            for i, row in enumerate(csv_reader):
                if i >= max_rows:
                    break
                rows.append(row)
            
            # Validar samples
            validation_warnings = []
            for i, row in enumerate(rows[:3]):  # Validar 3 primeiras
                warnings = self._validate_row(row, i + 2)  # +2 porque linha 1 é header
                if warnings:
                    validation_warnings.extend(warnings)
            
            return {
                'status': 'success',
                'headers': list(headers),
                'column_mapping': column_mapping,
                'sample_rows': rows,
                'total_rows_detected': len(rows),  # Aproximado
                'validation_warnings': validation_warnings,
                'delimiter': delimiter,
                'has_ddd_separated': 'DDD' in headers or 'ddd' in headers
            }
        
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _detect_delimiter(self, content):
        """
        Auto-detecta o delimitador do CSV
        
        Args:
            content: Conteúdo do arquivo CSV
            
        Returns:
            str: Delimitador detectado (',' ou ';')
        """
        first_line = content.split('\n')[0]
        
        # Contar vírgulas e ponto-e-vírgulas
        comma_count = first_line.count(',')
        semicolon_count = first_line.count(';')
        
        # Se tem mais ponto-e-vírgula, usar ponto-e-vírgula
        if semicolon_count > comma_count:
            return ';'
        
        return ','
    
    def _auto_map_columns(self, headers):
        """
        Mapeia automaticamente colunas CSV para campos do modelo
        
        Suporta formatos especiais:
        - Nome/name → name
        - DDD + Telefone → phone (combina automaticamente)
        - email/e-mail → email
        
        Args:
            headers: Lista de nomes de colunas do CSV
            
        Returns:
            dict: Mapeamento {coluna_csv: campo_modelo}
        """
        mapping = {}
        headers_lower = [h.lower().strip() if h else '' for h in headers]
        
        for header in headers:
            if not header:
                continue
                
            header_lower = header.lower().strip()
            
            # Casos especiais - Nome (com variações)
            if header_lower in ['nome', 'name', 'nome completo', 'nome_completo', 'nomecompleto', 'cliente', 'contato']:
                mapping[header] = 'name'
                continue
            
            # DDD é tratado separadamente
            if header_lower == 'ddd':
                mapping[header] = 'ddd'  # Marcador especial
                continue
            
            # Telefone (pode ser combinado com DDD)
            # ✅ CORREÇÃO: Adicionar variações com plural e maiúsculas
            if header_lower in ['telefone', 'telefones', 'phone', 'phones', 'fone', 'fones', 'celular', 'celulares', 'whatsapp']:
                mapping[header] = 'phone'
                continue
            
            # Email
            if header_lower in ['email', 'e-mail', 'mail']:
                mapping[header] = 'email'
                continue
            
            # Quem indicou
            if header_lower in ['quem indicou', 'indicado por', 'referral', 'referred_by']:
                mapping[header] = 'referred_by'
                continue
            
            # Campos demográficos
            if header_lower in ['cidade', 'city']:
                mapping[header] = 'city'
                continue
            
            if header_lower in ['estado', 'state', 'uf']:
                mapping[header] = 'state'
                continue
            
            # Campos de nascimento
            if header_lower in ['data_nascimento', 'nascimento', 'birth_date', 'aniversario']:
                mapping[header] = 'birth_date'
                continue
            
            # Observações/notas
            if header_lower in ['observacoes', 'obs', 'notas', 'notes', 'comentarios']:
                mapping[header] = 'notes'
                continue
            
            # CEP
            if header_lower in ['cep', 'zipcode', 'zip']:
                mapping[header] = 'zipcode'
                continue
            
            # Campos comerciais
            if header_lower in ['data_compra', 'data compra', 'ultima_compra', 'última compra']:
                mapping[header] = 'last_purchase_date'
                continue
            
            if header_lower in ['valor', 'valor_compra', 'valor compra', 'ultimo_valor']:
                mapping[header] = 'last_purchase_value'
                continue
            
            # Campos personalizados (não reconhecidos) → custom_fields
            # Mapear automaticamente para custom_fields.{nome_do_campo}
            mapping[header] = f'custom_fields.{header_lower}'
        
        return mapping
    
    def _validate_row(self, row, row_number):
        """
        Valida uma linha do CSV e retorna warnings/errors
        
        Args:
            row: Dicionário com dados da linha
            row_number: Número da linha (para referência)
            
        Returns:
            list: Lista de warnings/errors
        """
        warnings = []
        
        # Validar phone
        phone = row.get('phone') or row.get('telefone') or row.get('celular')
        if phone:
            try:
                normalized = normalize_phone(phone)
                if len(normalized) < 13 or len(normalized) > 14:
                    warnings.append({
                        'row': row_number,
                        'field': 'phone',
                        'value': phone,
                        'error': 'Telefone pode estar em formato incorreto',
                        'severity': 'warning'
                    })
            except:
                warnings.append({
                    'row': row_number,
                    'field': 'phone',
                    'value': phone,
                    'error': 'Telefone inválido',
                    'severity': 'critical'
                })
        
        # Validar email
        email = row.get('email')
        if email:
            try:
                validate_email(email)
            except:
                warnings.append({
                    'row': row_number,
                    'field': 'email',
                    'value': email,
                    'error': 'Email em formato inválido (será ignorado)',
                    'severity': 'warning'
                })
        
        # Validar state
        state = row.get('state') or row.get('estado') or row.get('uf')
        if state and state.upper() not in VALID_STATES:
            warnings.append({
                'row': row_number,
                'field': 'state',
                'value': state,
                'error': 'Estado/UF inválido (será ignorado)',
                'severity': 'warning'
            })
        
        return warnings
    
    def _remove_import_file(self, file_path):
        """Remove arquivo temporário de importação se existir (evita acúmulo em disco)."""
        import os
        if not file_path:
            return
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except OSError as e:
            logger.warning("Não foi possível remover arquivo temporário %s: %s", file_path, e)

    def process_csv_from_record(self, import_record):
        """
        Processa importação CSV a partir de um ContactImport já criado (arquivo em file_path).
        Usado pelo worker em background. Atualiza import_record em lugar.
        """
        import os

        opts = import_record.import_options or {}
        delimiter = opts.get('delimiter') or ','
        column_mapping = opts.get('column_mapping')

        try:
            with open(import_record.file_path, 'rb') as f:
                raw_content = f.read()
        except Exception as e:
            logger.exception("Erro ao abrir arquivo de importação: %s", import_record.file_path)
            import_record.status = ContactImport.Status.FAILED
            import_record.errors.append({'error': f'Não foi possível abrir o arquivo: {e}'})
            import_record.save()
            self._remove_import_file(import_record.file_path)
            return

        decoded_file = self._decode_file_content(raw_content)
        if not delimiter:
            delimiter = self._detect_delimiter(decoded_file)
        csv_reader = csv.DictReader(io.StringIO(decoded_file), delimiter=delimiter)
        if not column_mapping:
            column_mapping = self._auto_map_columns(csv_reader.fieldnames)
        rows = list(csv_reader)

        import_record.total_rows = len(rows)
        import_record.status = ContactImport.Status.PROCESSING
        import_record.save(update_fields=['total_rows', 'status'])

        for i, row in enumerate(rows):
            try:
                mapped_row = self._apply_column_mapping(row, column_mapping)
                self._process_row(mapped_row, import_record)
            except Exception as e:
                error_message = str(e)
                if 'unique constraint' in error_message.lower() and 'tag' in error_message.lower():
                    error_message = 'Tag já existe. Tente usar um nome diferente para a tag.'
                import_record.error_count += 1
                import_record.errors.append({
                    'row': i + 2,
                    'data': row,
                    'error': error_message
                })
            import_record.processed_rows = i + 1
            import_record.save(update_fields=['processed_rows', 'created_count', 'updated_count', 'skipped_count', 'error_count', 'errors'])

        import_record.status = ContactImport.Status.COMPLETED
        import_record.completed_at = timezone.now()
        import_record.save(update_fields=['status', 'completed_at'])
        self._remove_import_file(import_record.file_path)

    def process_csv(self, file, update_existing=False, auto_tag_id=None, delimiter=None, column_mapping=None):
        """
        Processa arquivo CSV e importa contatos (síncrono; preferir usar view assíncrona + process_csv_from_record).
        
        Mantido para compatibilidade. Em produção a view deve criar ContactImport e disparar thread.
        """
        # Criar registro de importação
        import_record = ContactImport.objects.create(
            tenant=self.tenant,
            file_name=file.name,
            file_path=f'imports/{self.tenant.id}/{file.name}',
            created_by=self.user,
            update_existing=update_existing,
            import_type=ContactImport.ImportType.CSV,
            import_options={'delimiter': delimiter or ',', 'column_mapping': column_mapping or {}}
        )
        
        if auto_tag_id:
            try:
                import_record.auto_tag_id = auto_tag_id
                import_record.save()
            except Exception:
                pass
        
        try:
            # Ler CSV com detecção automática de encoding
            raw_content = file.read()
            decoded_file = self._decode_file_content(raw_content)
            
            if not delimiter:
                delimiter = self._detect_delimiter(decoded_file)
            
            csv_reader = csv.DictReader(io.StringIO(decoded_file), delimiter=delimiter)
            
            if not column_mapping:
                column_mapping = self._auto_map_columns(csv_reader.fieldnames)
            
            rows = list(csv_reader)
            import_record.total_rows = len(rows)
            import_record.status = ContactImport.Status.PROCESSING
            import_record.save()
            
            for i, row in enumerate(rows):
                try:
                    if i == 0:
                        print(f"\n🔍 DEBUG - Primeira linha do CSV:")
                        print(f"   Row original: {row}")
                        print(f"   Column mapping: {column_mapping}")
                    
                    mapped_row = self._apply_column_mapping(row, column_mapping)
                    
                    if i == 0:
                        print(f"   Row mapeado: {mapped_row}")
                    
                    self._process_row(mapped_row, import_record)
                    import_record.processed_rows = i + 1
                    import_record.save()
                except Exception as e:
                    if i < 3:
                        print(f"❌ Erro linha {i+2}: {str(e)}")
                        print(f"   Row: {row}")
                    
                    error_message = str(e)
                    if 'unique constraint' in error_message.lower() and 'tag' in error_message.lower():
                        error_message = 'Tag já existe. Tente usar um nome diferente para a tag.'
                    
                    import_record.error_count += 1
                    import_record.errors.append({
                        'row': i + 2,
                        'data': row,
                        'error': error_message
                    })
                    import_record.save()
            
            import_record.status = ContactImport.Status.COMPLETED
            import_record.completed_at = timezone.now()
            import_record.save()
            
            return {
                'status': 'success',
                'import_id': str(import_record.id),
                'total_rows': import_record.total_rows,
                'created': import_record.created_count,
                'created_count': import_record.created_count,
                'updated': import_record.updated_count,
                'updated_count': import_record.updated_count,
                'skipped': import_record.skipped_count,
                'skipped_count': import_record.skipped_count,
                'errors': import_record.error_count,
                'error_count': import_record.error_count,
                'errors_list': import_record.errors if import_record.error_count > 0 else []
            }
        
        except Exception as e:
            import_record.status = ContactImport.Status.FAILED
            import_record.errors.append({'error': str(e)})
            import_record.save()
            
            print(f"❌ ERRO FATAL na importação CSV:")
            print(f"   Arquivo: {file.name}")
            print(f"   Tenant: {self.tenant.id}")
            print(f"   Erro: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                'status': 'error',
                'message': str(e),
                'import_id': str(import_record.id),
                'total_rows': 0,
                'created': 0,
                'updated': 0,
                'skipped': 0,
                'errors': 1,
                'error_count': 1,
                'errors_list': [{'row': 0, 'error': str(e)}]
            }

    def _apply_column_mapping(self, row, mapping):
        """
        Aplica o mapeamento de colunas ao row
        
        Args:
            row: Dict com dados originais do CSV
            mapping: Dict com mapeamento {coluna_csv: campo_modelo}
            
        Returns:
            dict: Row com chaves mapeadas
        """
        # Debug
        if not mapping:
            print(f"⚠️ WARNING: column_mapping is None! Using auto-detection")
            mapping = self._auto_map_columns(row.keys())
            print(f"   Auto-detected mapping: {mapping}")
        
        mapped = {}
        custom_fields = {}
        
        for csv_col, model_field in mapping.items():
            if model_field and model_field != 'ignorado':
                value = row.get(csv_col, '').strip()
                
                # Separar custom_fields dos campos padrão
                if model_field.startswith('custom_fields.'):
                    # Campo customizado
                    field_name = model_field.replace('custom_fields.', '')
                    if value:
                        custom_fields[field_name] = value
                else:
                    # Campo padrão
                    mapped[model_field] = value
        
        # Combinar DDD + Telefone se necessário
        if 'ddd' in mapped and 'phone' in mapped:
            ddd = str(mapped.get('ddd', '')).strip()
            phone = str(mapped.get('phone', '')).strip()
            if ddd and phone:
                mapped['phone'] = f"{ddd}{phone}"
        
        # Adicionar custom_fields ao mapped
        if custom_fields:
            mapped['custom_fields'] = custom_fields
        
        # Debug primeira linha - mostrar TODOS os campos mapeados
        if mapped.get('name'):
            debug_fields = {
                'name': mapped.get('name'),
                'phone': mapped.get('phone'),
                'email': mapped.get('email'),
                'last_purchase_date': mapped.get('last_purchase_date'),
                'last_purchase_value': mapped.get('last_purchase_value'),
                'custom_fields': custom_fields
            }
            print(f"✅ Row mapeado: {debug_fields}")
        
        return mapped
    
    def _process_row(self, row, import_record):
        """Processa uma linha do CSV (row já mapeado)"""
        
        # Extrair nome (obrigatório) - agora do row mapeado
        name = row.get('name', '').strip()
        if not name:
            raise ValueError('Campo "Nome" é obrigatório')
        
        # Extrair telefone (já combinado pelo _apply_column_mapping se DDD estava separado)
        phone_raw = row.get('phone', '').strip()
        if not phone_raw:
            raise ValueError('Campo "Telefone" é obrigatório')
        
        # Normalizar telefone para formato E.164
        phone = normalize_phone(phone_raw)
        
        # Verificar duplicata - SEMPRE verificar por telefone normalizado
        # Usar get_or_create para evitar race conditions
        try:
            existing = Contact.objects.get(
                tenant=self.tenant,
                phone=phone
            )
            
            # Contato já existe - atualizar ou pular
            if import_record.update_existing:
                # Atualizar contato existente
                self._update_contact(existing, row)
                import_record.updated_count += 1
                
                # Adicionar auto-tag se não tiver
                if import_record.auto_tag and import_record.auto_tag not in existing.tags.all():
                    existing.tags.add(import_record.auto_tag)
            else:
                # Pular contato existente
                import_record.skipped_count += 1
                
        except Contact.DoesNotExist:
            # Contato não existe - criar novo
            try:
                contact = self._create_contact(row, phone)
                import_record.created_count += 1
                
                # Adicionar auto-tag
                if import_record.auto_tag:
                    contact.tags.add(import_record.auto_tag)
            except Exception as e:
                # Se der erro de unique constraint (telefone duplicado), tentar atualizar
                error_str = str(e).lower()
                if 'unique constraint' in error_str or 'duplicate key' in error_str or 'unique_together' in error_str:
                    # Tentar buscar novamente (pode ter sido criado em outra thread)
                    try:
                        existing = Contact.objects.get(tenant=self.tenant, phone=phone)
                        if import_record.update_existing:
                            self._update_contact(existing, row)
                            import_record.updated_count += 1
                        else:
                            import_record.skipped_count += 1
                    except Contact.DoesNotExist:
                        # Se ainda não existe, re-lançar o erro original
                        raise
                else:
                    # Outro tipo de erro, re-lançar
                    raise
    
    def _create_contact(self, row, phone):
        """Cria novo contato a partir do CSV (row já mapeado)"""
        
        # Extrair campos (row já está mapeado)
        name = row.get('name', '').strip()
        email = row.get('email', '').strip() or None
        notes = row.get('notes', '').strip()
        city = row.get('city', '').strip() or None
        state = row.get('state', '').strip() or None
        
        # 🆕 Inferir estado pelo DDD se não fornecido
        if not state:
            # Tentar obter DDD (pode estar em 'ddd' ou extrair de 'phone')
            ddd = row.get('ddd', '').strip()
            if not ddd:
                # Tentar extrair do telefone
                ddd = extract_ddd_from_phone(phone)
            
            # Se encontrou DDD, inferir estado
            if ddd:
                inferred_state = get_state_from_ddd(ddd)
                if inferred_state:
                    state = inferred_state
                    print(f"  ℹ️  Estado '{state}' inferido pelo DDD {ddd}")
        
        # Extrair custom_fields
        custom_fields = row.get('custom_fields', {})
        if not isinstance(custom_fields, dict):
            custom_fields = {}
        
        contact = Contact.objects.create(
            tenant=self.tenant,
            phone=phone,
            name=name,
            email=email if email else None,
            birth_date=self._parse_date(row.get('birth_date')),
            gender=row.get('gender'),
            city=city,
            state=state.upper() if state and len(state) == 2 else None,
            country=row.get('country') or 'BR',
            zipcode=row.get('zipcode'),
            last_purchase_date=self._parse_date(row.get('last_purchase_date')),
            last_purchase_value=self._parse_decimal(row.get('last_purchase_value')),
            total_purchases=self._parse_int(row.get('total_purchases'), 0),
            lifetime_value=self._parse_decimal(row.get('lifetime_value'), Decimal('0')),
            notes=notes if notes else '',
            referred_by=row.get('referred_by'),
            custom_fields=custom_fields,  # ✅ Adicionar custom_fields
            source='import',
            created_by=self.user
        )
        
        return contact
    
    def _update_contact(self, contact, row):
        """Atualiza contato existente com dados do CSV (row já mapeado)"""
        
        # Atualizar nome (row já está mapeado, usar 'name')
        name = row.get('name', '').strip()
        if name:
            contact.name = name
        
        # Atualizar email
        email = row.get('email', '').strip()
        if email:
            contact.email = email
        
        # Atualizar data de nascimento
        birth_date = row.get('birth_date')
        if birth_date:
            parsed = self._parse_date(birth_date)
            if parsed:
                contact.birth_date = parsed
        
        # Atualizar cidade
        city = row.get('city', '').strip()
        if city:
            contact.city = city
        
        # Atualizar estado
        state = row.get('state', '').strip()
        if state and len(state) == 2:
            contact.state = state.upper()
        elif not state:
            # Tentar inferir estado pelo DDD do telefone
            ddd = extract_ddd_from_phone(contact.phone)
            if ddd:
                inferred_state = get_state_from_ddd(ddd)
                if inferred_state:
                    contact.state = inferred_state
        
        # Atualizar país
        country = row.get('country')
        if country:
            contact.country = country
        
        # Atualizar CEP
        zipcode = row.get('zipcode', '').strip()
        if zipcode:
            contact.zipcode = zipcode
        
        # Atualizar gênero
        gender = row.get('gender')
        if gender:
            contact.gender = gender
        
        # Atualizar data da última compra
        last_purchase_date = row.get('last_purchase_date')
        if last_purchase_date:
            parsed = self._parse_date(last_purchase_date)
            if parsed:
                contact.last_purchase_date = parsed
        
        # Atualizar valor da última compra
        last_purchase_value = row.get('last_purchase_value')
        if last_purchase_value:
            parsed = self._parse_decimal(last_purchase_value)
            if parsed is not None:
                contact.last_purchase_value = parsed
        
        # Atualizar total de compras
        total_purchases = row.get('total_purchases')
        if total_purchases is not None:
            parsed = self._parse_int(total_purchases)
            if parsed is not None:
                contact.total_purchases = parsed
        
        # Atualizar LTV
        lifetime_value = row.get('lifetime_value')
        if lifetime_value:
            parsed = self._parse_decimal(lifetime_value)
            if parsed is not None:
                contact.lifetime_value = parsed
        
        # Atualizar notes (append se já existir)
        notes = row.get('notes', '').strip()
        if notes:
            if contact.notes:
                contact.notes += f"\n{notes}"
            else:
                contact.notes = notes
        
        # Atualizar quem indicou
        referred_by = row.get('referred_by', '').strip()
        if referred_by:
            contact.referred_by = referred_by
        
        # Atualizar custom_fields (merge, não sobrescrever)
        custom_fields = row.get('custom_fields', {})
        if custom_fields and isinstance(custom_fields, dict):
            if not contact.custom_fields:
                contact.custom_fields = {}
            contact.custom_fields.update(custom_fields)
        
        # Atualizar source para 'import' se ainda não for
        if contact.source != 'import':
            contact.source = 'import'
        
        contact.save()
    
    def _parse_date(self, value):
        """Parse date string to date object"""
        if not value:
            return None
        try:
            # Tentar vários formatos
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                try:
                    return datetime.strptime(value, fmt).date()
                except:
                    continue
            return None
        except:
            return None
    
    def _parse_decimal(self, value, default=None):
        """Parse decimal string"""
        if not value:
            return default
        try:
            # Remover símbolos de moeda, espaços e converter vírgula para ponto
            clean = str(value).replace('R$', '').replace(' ', '').replace(',', '.').strip()
            # Remover pontos que são separadores de milhar (ex: "1.500,00" -> "1500.00")
            if clean.count('.') > 1:
                # Se tem múltiplos pontos, o último é decimal, os outros são milhares
                parts = clean.split('.')
                clean = ''.join(parts[:-1]) + '.' + parts[-1]
            return Decimal(clean)
        except (InvalidOperation, ValueError) as e:
            print(f"⚠️ Erro ao parsear decimal '{value}': {e}")
            return default
    
    def _parse_int(self, value, default=0):
        """Parse int string"""
        if not value:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default


def run_import_from_record(import_id):
    """
    Processa uma importação em background (chamado pela thread).
    Carrega o ContactImport, abre o arquivo em file_path e delega para CSV ou VCF.
    """
    try:
        import_record = ContactImport.objects.get(id=import_id)
    except ContactImport.DoesNotExist:
        logger.error("ContactImport não encontrado: %s", import_id)
        return
    tenant = import_record.tenant
    user = import_record.created_by
    try:
        if import_record.import_type == ContactImport.ImportType.VCF.value:
            svc = ContactVcfImportService(tenant=tenant, user=user)
            svc.process_vcf_from_record(import_record)
        else:
            svc = ContactImportService(tenant=tenant, user=user)
            svc.process_csv_from_record(import_record)
    except Exception as e:
        logger.exception("Erro fatal na importação %s: %s", import_id, e)
        import_record.refresh_from_db()
        import_record.status = ContactImport.Status.FAILED
        import_record.errors.append({'error': str(e)})
        import_record.save(update_fields=['status', 'errors'])
        # Remover arquivo temporário também em caso de falha (evita acúmulo)
        _path = getattr(import_record, 'file_path', None)
        if _path:
            try:
                import os
                if os.path.isfile(_path):
                    os.remove(_path)
            except OSError as err:
                logger.warning("Não foi possível remover arquivo temporário após falha: %s", err)


class ContactVcfImportService(ContactImportService):
    """Importação de contatos a partir de arquivos VCF (vCard)."""

    def _parse_vcard_date(self, value):
        """Parse BDAY do vCard (YYYY-MM-DD ou --MM-DD)."""
        if not value or not value.strip():
            return None
        value = value.strip()
        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '--%m-%d']:
            try:
                return datetime.strptime(value.replace('--', '1900-'), fmt).date()
            except ValueError:
                continue
        return None

    def _vcard_to_row(self, card):
        """Converte um vCard (vobject) em dict no formato do Contact (name, phone, email, ...)."""
        row = {}
        # FN (Formatted Name) ou N (structured name)
        fn = getattr(card, 'fn', None)
        if fn and fn.value:
            row['name'] = fn.value.strip()
        else:
            n = getattr(card, 'n', None)
            if n and n.value:
                parts = getattr(n.value, 'given', '') or '', getattr(n.value, 'family', '') or ''
                row['name'] = ' '.join(p for p in parts if p).strip() or ''
        if not row.get('name'):
            row['name'] = 'Sem nome'

        # TEL - preferir CELL, depois WORK, depois o primeiro
        tels = card.contents.get('tel', [])
        phone_val = None
        for t in tels:
            val = getattr(t, 'value', None) or (t.value if hasattr(t, 'value') else None)
            if val:
                phone_val = val.strip().replace(' ', '').replace('-', '')
                break
        row['phone'] = phone_val or ''

        # EMAIL
        emails = card.contents.get('email', [])
        if emails:
            em = emails[0]
            val = getattr(em, 'value', None)
            if val:
                row['email'] = val.strip()

        # BDAY
        bday = card.contents.get('bday', [])
        if bday:
            row['birth_date'] = self._parse_vcard_date(str(bday[0].value)) if bday[0].value else None

        # ADR (pode ser objeto com .locality ou lista [pobox, street, locality, region, code, country])
        adrs = card.contents.get('adr', [])
        if adrs:
            adr = adrs[0].value
            if isinstance(adr, (list, tuple)) and len(adr) >= 7:
                row['city'] = (adr[3] or '').strip() or None
                row['state'] = (adr[4] or '').strip() or None
                row['zipcode'] = (adr[5] or '').strip() or None
                row['country'] = (adr[6] or '').strip() or None
            elif hasattr(adr, 'locality'):
                row['city'] = (getattr(adr, 'locality', '') or '').strip() or None
                row['state'] = (getattr(adr, 'region', '') or '').strip() or None
                row['zipcode'] = (getattr(adr, 'code', '') or '').strip() or None
                row['country'] = (getattr(adr, 'country', '') or '').strip() or None

        # NOTE + campos extras em notes (leitura defensiva via contents para evitar vCards malformados)
        notes_parts = []
        note = card.contents.get('note', [])
        if note and getattr(note[0], 'value', None):
            notes_parts.append(note[0].value.strip())
        extras = []
        for prop, label in (
            ('org', 'Org'),
            ('title', 'Cargo'),
            ('url', 'URL'),
            ('nickname', 'Apelido'),
        ):
            items = card.contents.get(prop, [])
            if not items:
                continue
            raw_val = getattr(items[0], 'value', None)
            if raw_val is None:
                continue
            # vobject pode retornar lista (ex.: ORG) ou string
            if isinstance(raw_val, (list, tuple)):
                val = (raw_val[0] if raw_val else '')
            else:
                val = raw_val
            val = str(val).strip()
            if val:
                extras.append(f"{label}: {val}")
        if extras:
            notes_parts.append('\n'.join(extras))
        row['notes'] = '\n'.join(notes_parts) if notes_parts else ''

        return row

    def preview_vcf(self, file, max_entries=10):
        """Gera preview do VCF para exibir antes de importar."""
        try:
            import vobject
        except ImportError:
            return {'status': 'error', 'error': 'Biblioteca vobject não instalada. pip install vobject'}
        raw = file.read()
        file.seek(0)
        decoded = self._decode_file_content(raw)
        samples = []
        total = 0
        total_with_phone = 0
        try:
            for card in vobject.readComponents(io.StringIO(decoded)):
                total += 1
                row = self._vcard_to_row(card)
                if row.get('phone'):
                    total_with_phone += 1
                    if len(samples) < max_entries:
                        samples.append(row)
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
        return {
            'status': 'success',
            'headers': ['name', 'phone', 'email', 'city', 'state', 'notes'],
            'column_mapping': {},
            'sample_rows': samples,
            'total_rows_detected': total,
            'total_with_phone': total_with_phone,
            'validation_warnings': [],
            'source': 'vcf',
        }

    def process_vcf_from_record(self, import_record):
        """Processa importação VCF a partir de um ContactImport já criado (arquivo em file_path)."""
        try:
            import vobject
        except ImportError:
            import_record.status = ContactImport.Status.FAILED
            import_record.errors.append({'error': 'Biblioteca vobject não instalada'})
            import_record.save()
            return
        try:
            with open(import_record.file_path, 'rb') as f:
                raw = f.read()
        except Exception as e:
            logger.exception("Erro ao abrir arquivo VCF: %s", import_record.file_path)
            import_record.status = ContactImport.Status.FAILED
            import_record.errors.append({'error': f'Não foi possível abrir o arquivo: {e}'})
            import_record.save()
            self._remove_import_file(import_record.file_path)
            return
        decoded = self._decode_file_content(raw)
        cards = list(vobject.readComponents(io.StringIO(decoded)))
        import_record.total_rows = len(cards)
        import_record.status = ContactImport.Status.PROCESSING
        import_record.save(update_fields=['total_rows', 'status'])

        if len(cards) == 0:
            import_record.status = ContactImport.Status.COMPLETED
            import_record.completed_at = timezone.now()
            import_record.errors.append({'error': 'Nenhum contato encontrado no arquivo VCF'})
            import_record.save(update_fields=['status', 'completed_at', 'errors'])
            self._remove_import_file(import_record.file_path)
            return

        for i, card in enumerate(cards):
            try:
                row = self._vcard_to_row(card)
                phone_raw = (row.get('phone') or '').strip()
                if not phone_raw:
                    import_record.error_count += 1
                    import_record.errors.append({'row': i + 1, 'error': 'Telefone obrigatório', 'data': row})
                    import_record.processed_rows = i + 1
                    import_record.save(update_fields=['processed_rows', 'error_count', 'errors'])
                    continue
                phone = normalize_phone(phone_raw)
                row['phone'] = phone
                self._process_row(row, import_record)
            except Exception as e:
                import_record.error_count += 1
                import_record.errors.append({'row': i + 1, 'error': str(e)})
            import_record.processed_rows = i + 1
            import_record.save(update_fields=['processed_rows', 'created_count', 'updated_count', 'skipped_count', 'error_count', 'errors'])

        import_record.status = ContactImport.Status.COMPLETED
        import_record.completed_at = timezone.now()
        import_record.save(update_fields=['status', 'completed_at'])
        self._remove_import_file(import_record.file_path)


class ContactExportService:
    """Service para exportação de contatos para CSV"""
    
    def export_to_csv(self, contacts):
        """
        Exporta contatos para CSV
        
        Args:
            contacts: QuerySet de contatos
            
        Returns:
            str: Conteúdo do arquivo CSV
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'name', 'phone', 'email', 'birth_date',
            'gender', 'city', 'state', 'country', 'zipcode',
            'last_purchase_date', 'last_purchase_value', 'total_purchases',
            'lifetime_value', 'average_ticket',
            'lifecycle_stage', 'engagement_score',
            'notes', 'created_at'
        ])
        
        # Data
        for contact in contacts:
            writer.writerow([
                contact.name,
                contact.phone,
                contact.email or '',
                contact.birth_date.isoformat() if contact.birth_date else '',
                contact.get_gender_display() if contact.gender else '',
                contact.city or '',
                contact.state or '',
                contact.country,
                contact.zipcode or '',
                contact.last_purchase_date.isoformat() if contact.last_purchase_date else '',
                str(contact.last_purchase_value) if contact.last_purchase_value else '',
                contact.total_purchases,
                str(contact.lifetime_value),
                str(contact.average_ticket),
                contact.lifecycle_stage,
                contact.engagement_score,
                contact.notes,
                contact.created_at.isoformat()
            ])
        
        return output.getvalue()


