/**
 * Baixa um anexo via fetch + blob para forçar download sem abrir nova aba.
 * Usado no menu de contexto (Baixar), lightbox de imagem e ícone de documento.
 */
export async function downloadAttachment(
  fileUrl: string,
  filename: string
): Promise<boolean> {
  try {
    const response = await fetch(fileUrl);
    if (!response.ok) return false;

    const blob = await response.blob();
    if (!blob || blob.size === 0) return false;

    const blobUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename || 'arquivo';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    return true;
  } catch {
    return false;
  }
}
