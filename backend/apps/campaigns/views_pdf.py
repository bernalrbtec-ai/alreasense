"""
View para gerar PDF de relatório de campanha
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

from .models import Campaign, CampaignContact, CampaignLog

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_campaign_pdf(request, campaign_id):
    """
    Gera PDF do relatório completo da campanha
    
    GET /api/campaigns/{campaign_id}/export-pdf/
    """
    try:
        user = request.user
        tenant = user.tenant
        
        # Buscar campanha
        campaign = get_object_or_404(
            Campaign.objects.select_related('created_by', 'tenant'),
            id=campaign_id,
            tenant=tenant
        )
        
        # Buscar todos os contatos da campanha com informações completas
        campaign_contacts = CampaignContact.objects.filter(
            campaign=campaign
        ).select_related(
            'contact',
            'instance_used',
            'message_used'
        ).order_by('sent_at', 'created_at')
        
        # Buscar logs para estatísticas
        logs = CampaignLog.objects.filter(campaign=campaign)
        
        # Calcular estatísticas
        total_sent = logs.filter(log_type='message_sent').count()
        total_delivered = logs.filter(log_type='message_delivered').count()
        total_read = logs.filter(log_type='message_read').count()
        total_failed = logs.filter(log_type='message_failed').count()
        
        # Criar buffer para PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=12,
            spaceBefore=12
        )
        
        normal_style = styles['Normal']
        normal_style.fontSize = 10
        
        # ============================================================
        # PRIMEIRA PÁGINA: RELATÓRIO SINTÉTICO
        # ============================================================
        
        # Título
        story.append(Paragraph("Relatório de Campanha", title_style))
        story.append(Spacer(1, 0.5*cm))
        
        # Informações básicas
        info_data = [
            ['Campanha:', campaign.name],
            ['Criado por:', campaign.created_by.get_full_name() if campaign.created_by else 'Sistema'],
            ['Data de Criação:', campaign.created_at.strftime('%d/%m/%Y %H:%M:%S') if campaign.created_at else 'N/A'],
            ['Início:', campaign.started_at.strftime('%d/%m/%Y %H:%M:%S') if campaign.started_at else 'Não iniciada'],
            ['Quantidade de Contatos:', str(campaign.total_contacts)],
            ['Status:', campaign.get_status_display()],
        ]
        
        info_table = Table(info_data, colWidths=[5*cm, 12*cm])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 1*cm))
        
        # Gráficos de estatísticas
        story.append(Paragraph("Estatísticas de Envio", heading_style))
        
        # Tabela de estatísticas
        stats_data = [
            ['Métrica', 'Quantidade', 'Percentual'],
            ['Enviadas', str(total_sent), f'{(total_sent/campaign.total_contacts*100) if campaign.total_contacts > 0 else 0:.1f}%'],
            ['Entregues', str(total_delivered), f'{(total_delivered/campaign.total_contacts*100) if campaign.total_contacts > 0 else 0:.1f}%'],
            ['Lidas', str(total_read), f'{(total_read/campaign.total_contacts*100) if campaign.total_contacts > 0 else 0:.1f}%'],
            ['Falhas', str(total_failed), f'{(total_failed/campaign.total_contacts*100) if campaign.total_contacts > 0 else 0:.1f}%'],
        ]
        
        stats_table = Table(stats_data, colWidths=[6*cm, 5*cm, 6*cm])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#dbeafe')),  # Entregues
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#e9d5ff')),  # Lidas
            ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#fee2e2')),  # Falhas
        ]))
        
        story.append(stats_table)
        story.append(Spacer(1, 0.5*cm))
        
        # Observação sobre leituras
        obs_style = ParagraphStyle(
            'Observation',
            parent=normal_style,
            fontSize=9,
            textColor=colors.HexColor('#6b7280'),
            fontStyle='italic',
            alignment=TA_LEFT
        )
        story.append(Paragraph(
            "<b>Observação:</b> As leituras são apenas referência, pois dependem do WhatsApp do destinatário reportar o status.",
            obs_style
        ))
        
        # Nova página para relatório detalhado
        story.append(PageBreak())
        
        # ============================================================
        # SEGUNDA PÁGINA: RELATÓRIO DETALHADO POR CONTATO
        # ============================================================
        
        story.append(Paragraph("Relatório Detalhado por Contato", heading_style))
        
        # Cabeçalho da tabela
        header_data = [['Contato', 'Número', 'Hora do Disparo', 'Hora da Entrega', 'Visualizado', 'OBS']]
        
        # Dados dos contatos
        contact_rows = []
        for cc in campaign_contacts:
            contact_name = cc.contact.name if cc.contact else 'N/A'
            contact_phone = cc.contact.phone if cc.contact else 'N/A'
            
            # Formatar timestamps
            sent_time = cc.sent_at.strftime('%d/%m/%Y %H:%M:%S') if cc.sent_at else '-'
            delivered_time = cc.delivered_at.strftime('%d/%m/%Y %H:%M:%S') if cc.delivered_at else '-'
            read_time = cc.read_at.strftime('%d/%m/%Y %H:%M:%S') if cc.read_at else '-'
            visualizado = 'Sim' if cc.read_at else ('Entregue' if cc.delivered_at else 'Não')
            
            # Observações
            obs = ''
            if cc.error_message:
                obs = f"Erro: {cc.error_message[:50]}"
            elif cc.status == 'failed':
                obs = 'Falha no envio'
            elif cc.retry_count > 0:
                obs = f'{cc.retry_count} tentativa(s)'
            
            contact_rows.append([
                contact_name,
                contact_phone,
                sent_time,
                delivered_time,
                visualizado,
                obs
            ])
        
        # Combinar cabeçalho com dados
        table_data = header_data + contact_rows
        
        # Criar tabela (ajustar larguras para A4)
        contact_table = Table(table_data, colWidths=[4*cm, 3*cm, 3*cm, 3*cm, 2.5*cm, 4.5*cm])
        contact_table.setStyle(TableStyle([
            # Cabeçalho
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            
            # Linhas alternadas
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
            
            # Fonte e padding das células
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            
            # Quebra de linha automática
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        story.append(contact_table)
        
        # Construir PDF
        doc.build(story)
        
        # Preparar resposta
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="campanha_{campaign.name.replace(" ", "_")}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        
        return response
        
    except Exception as e:
        logger.error(f"❌ [PDF] Erro ao gerar PDF da campanha {campaign_id}: {e}", exc_info=True)
        return Response({
            'error': f'Erro ao gerar PDF: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

