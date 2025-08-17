document.addEventListener('DOMContentLoaded', () => {
  const uploadBtn = document.getElementById('upload');
  const fileInput = document.getElementById('fileInput');
  const result = document.getElementById('fileResult');
  const pdfFrame = document.getElementById('pdfViewer');

  uploadBtn.addEventListener('click', () => fileInput.click());

  fileInput.addEventListener('change', async () => {
    if (!fileInput.files?.length) return;
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);

    const resp = await fetch('/process-audio/', { method: 'POST', body: fd });
    const data = await resp.json();

    result.innerHTML = `
      <p class="font-semibold">Transkript:</p>
      <p class="mb-2">${data.transcript}</p>
      <p class="font-semibold">Rechnungsdaten:</p>
      <pre class="bg-gray-100 p-2 rounded text-sm">${JSON.stringify(data.invoice, null, 2)}</pre>
    `;

    if (data.pdf_url) {
      pdfFrame.src = data.pdf_url;
      pdfFrame.classList.remove('hidden');
    }

    fileInput.value = '';
  });
});
