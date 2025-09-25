document.addEventListener('DOMContentLoaded', () => {
  const uploadBtn = document.getElementById('uploadImage');
  const fileInput = document.getElementById('imageInput');
  const result = document.getElementById('fileResult');
  const pdfFrame = document.getElementById('pdfViewer');

  if (!uploadBtn || !fileInput) return;

  uploadBtn.addEventListener('click', () => fileInput.click());

  fileInput.addEventListener('change', async () => {
    if (!fileInput.files?.length) return;
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);

    let data;
    try {
      const resp = await fetch('/process-image/', { method: 'POST', body: fd });
      data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || 'Fehler beim Verarbeiten');
      }
    } catch (err) {
      result.textContent = err.message;
      fileInput.value = '';
      return;
    }

    const transcript = data.transcript ?? 'Keine Transkription erkannt.';
    const invoice = data.invoice
      ? JSON.stringify(data.invoice, null, 2)
      : 'Keine Rechnungsdaten extrahiert.';

    result.innerHTML = `
      <p class="font-semibold">Transkript:</p>
      <p class="mb-2">${transcript}</p>
      <p class="font-semibold">Rechnungsdaten:</p>
      <pre class="bg-gray-100 p-2 rounded text-sm">${invoice}</pre>
    `;

    if (data.pdf_url) {
      pdfFrame.src = data.pdf_url;
      pdfFrame.classList.remove('hidden');
    }

    fileInput.value = '';
  });
});
