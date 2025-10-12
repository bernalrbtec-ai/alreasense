"""
Services para importação e exportação de contatos
"""

import csv
import io
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.utils import timezone
from django.db import transaction
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Contact, ContactImport, Tag
from .utils import normalize_phone, get_state_from_ddd, extract_ddd_from_phone, get_state_from_phone


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
            # Ler CSV
            decoded_file = file.read().decode('utf-8-sig')
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
            
            # Casos especiais
            if header_lower in ['nome', 'name']:
                mapping[header] = 'name'
                continue
            
            # DDD é tratado separadamente
            if header_lower == 'ddd':
                mapping[header] = 'ddd'  # Marcador especial
                continue
            
            # Telefone (pode ser combinado com DDD)
            if header_lower in ['telefone', 'phone', 'fone', 'celular', 'whatsapp']:
                mapping[header] = 'phone'
                continue
            
            # Email
            if header_lower in ['email', 'e-mail', 'mail']:
                mapping[header] = 'email'
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
            
            # Campos personalizados (não reconhecidos)
            # Ignorar por padrão, mas manter no mapeamento para o usuário poder escolher
            mapping[header] = None
        
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
    
    def process_csv(self, file, update_existing=False, auto_tag_id=None, delimiter=None, column_mapping=None):
        """
        Processa arquivo CSV e importa contatos
        
        Args:
            file: Arquivo CSV (UploadedFile)
            update_existing: Se True, atualiza contatos duplicados
            auto_tag_id: ID da tag para adicionar automaticamente
            delimiter: Delimitador do CSV (auto-detecta se None)
            column_mapping: Mapeamento de colunas (do preview)
        
        Returns:
            dict: Resultado da importação
        """
        # Criar registro de importação
        import_record = ContactImport.objects.create(
            tenant=self.tenant,
            file_name=file.name,
            file_path=f'imports/{self.tenant.id}/{file.name}',
            created_by=self.user,
            update_existing=update_existing
        )
        
        if auto_tag_id:
            try:
                import_record.auto_tag_id = auto_tag_id
                import_record.save()
            except:
                pass
        
        try:
            # Ler CSV
            decoded_file = file.read().decode('utf-8-sig')  # utf-8-sig remove BOM
            
            # Auto-detectar delimitador se não fornecido
            if not delimiter:
                delimiter = self._detect_delimiter(decoded_file)
            
            csv_reader = csv.DictReader(io.StringIO(decoded_file), delimiter=delimiter)
            
            # Se não tem mapeamento, criar automaticamente
            if not column_mapping:
                column_mapping = self._auto_map_columns(csv_reader.fieldnames)
            
            rows = list(csv_reader)
            import_record.total_rows = len(rows)
            import_record.status = ContactImport.Status.PROCESSING
            import_record.save()
            
            # Processar cada linha
            for i, row in enumerate(rows):
                try:
                    # Debug primeira linha
                    if i == 0:
                        print(f"\n🔍 DEBUG - Primeira linha do CSV:")
                        print(f"   Row original: {row}")
                        print(f"   Column mapping: {column_mapping}")
                    
                    # Aplicar mapeamento de colunas
                    mapped_row = self._apply_column_mapping(row, column_mapping)
                    
                    # Debug primeira linha mapeada
                    if i == 0:
                        print(f"   Row mapeado: {mapped_row}")
                    
                    self._process_row(mapped_row, import_record)
                    import_record.processed_rows = i + 1
                    import_record.save()
                except Exception as e:
                    # Debug erro
                    if i < 3:  # Mostrar primeiros 3 erros
                        print(f"❌ Erro linha {i+2}: {str(e)}")
                        print(f"   Row: {row}")
                    
                    import_record.error_count += 1
                    import_record.errors.append({
                        'row': i + 2,  # +2 porque linha 1 é header
                        'data': row,
                        'error': str(e)
                    })
                    import_record.save()
            
            # Finalizar
            import_record.status = ContactImport.Status.COMPLETED
            import_record.completed_at = timezone.now()
            import_record.save()
            
            return {
                'status': 'success',
                'import_id': str(import_record.id),
                'total_rows': import_record.total_rows,
                'created': import_record.created_count,
                'updated': import_record.updated_count,
                'skipped': import_record.skipped_count,
                'errors': import_record.error_count,
                'errors_list': import_record.errors if import_record.error_count > 0 else []
            }
        
        except Exception as e:
            import_record.status = ContactImport.Status.FAILED
            import_record.errors.append({'error': str(e)})
            import_record.save()
            
            return {
                'status': 'failed',
                'error': str(e)
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
        
        for csv_col, model_field in mapping.items():
            if model_field and model_field != 'ignorado':
                value = row.get(csv_col, '')
                mapped[model_field] = value
        
        # Combinar DDD + Telefone se necessário
        if 'ddd' in mapped and 'phone' in mapped:
            ddd = str(mapped.get('ddd', '')).strip()
            phone = str(mapped.get('phone', '')).strip()
            if ddd and phone:
                mapped['phone'] = f"{ddd}{phone}"
        
        # Debug primeira linha
        if mapped.get('name'):
            print(f"✅ Row mapeado: name={mapped.get('name')}, phone={mapped.get('phone')}, ddd={mapped.get('ddd', 'N/A')}")
        
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
        
        # Verificar duplicata
        existing = Contact.objects.filter(
            tenant=self.tenant,
            phone=phone
        ).first()
        
        if existing:
            if import_record.update_existing:
                # Atualizar
                self._update_contact(existing, row)
                import_record.updated_count += 1
            else:
                # Pular
                import_record.skipped_count += 1
        else:
            # Criar novo
            contact = self._create_contact(row, phone)
            import_record.created_count += 1
            
            # Adicionar auto-tag
            if import_record.auto_tag:
                contact.tags.add(import_record.auto_tag)
    
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
            source='import',
            created_by=self.user
        )
        
        return contact
    
    def _update_contact(self, contact, row):
        """Atualiza contato existente"""
        
        # Atualizar apenas campos não vazios
        name = row.get('Nome') or row.get('name') or row.get('nome')
        if name and name.strip():
            contact.name = name.strip()
        
        email = row.get('email') or row.get('Email') or row.get('e-mail')
        if email and email.strip():
            contact.email = email.strip()
        
        birth_date = row.get('birth_date') or row.get('data_nascimento')
        if birth_date:
            parsed = self._parse_date(birth_date)
            if parsed:
                contact.birth_date = parsed
        
        city = row.get('city') or row.get('cidade') or row.get('Cidade')
        if city and city.strip():
            contact.city = city.strip()
        
        state = row.get('state') or row.get('estado') or row.get('uf')
        if state and len(state) == 2:
            contact.state = state.upper()
        
        notes = row.get('notes') or row.get('observacoes') or row.get('Quem Indicou')
        if notes and notes.strip():
            # Append notes se já existir (não sobrescrever)
            if contact.notes:
                contact.notes += f"\n{notes.strip()}"
            else:
                contact.notes = notes.strip()
        
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
            # Remover símbolos de moeda e espaços
            clean = value.replace('R$', '').replace(',', '.').strip()
            return Decimal(clean)
        except (InvalidOperation, ValueError):
            return default
    
    def _parse_int(self, value, default=0):
        """Parse int string"""
        if not value:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default


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


