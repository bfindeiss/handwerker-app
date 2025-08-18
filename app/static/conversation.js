
document.addEventListener('DOMContentLoaded', () => {
  const recordBtn = document.getElementById('record');
  const status = document.getElementById('status');
  const chat = document.getElementById('chat');
  const pdfFrame = document.getElementById('pdfViewer');

  const sessionId = crypto.randomUUID();
  let recorder;
  let audioStream;
  let fullTranscript = '';

  function addMessage(text, sender) {
    const wrapper = document.createElement('div');
    wrapper.className = sender === 'user' ? 'flex justify-end' : 'flex justify-start';
    const bubble = document.createElement('div');
    bubble.className =
      'px-4 py-2 rounded-lg max-w-xs shadow ' +
      (sender === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-200');
    bubble.textContent = text;
    wrapper.appendChild(bubble);
    chat.appendChild(wrapper);
    chat.scrollTop = chat.scrollHeight;
  }

  recordBtn.addEventListener('click', async () => {
    if (!recordBtn.classList.contains('recording')) {
      audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          noiseSuppression: true,
          echoCancellation: true,
        },
      });
      const audioContext = new AudioContext({ sampleRate: 16000 });
      const input = audioContext.createMediaStreamSource(audioStream);
      recorder = new Recorder(input, { numChannels: 1 });
      recorder.record();
      recordBtn.classList.add('recording', 'bg-red-600');
      status.textContent = 'Aufnahme läuft...';
    } else {
      recorder.stop();
      audioStream.getTracks().forEach((t) => t.stop());
      recordBtn.classList.remove('recording', 'bg-red-600');
      status.textContent = 'Verarbeite...';
      recorder.exportWAV(sendAudio);
    }
  });

  async function sendAudio(blob) {
    const fd = new FormData();
    fd.append('session_id', sessionId);
    fd.append('file', blob, 'audio.wav');
    const resp = await fetch('/conversation/', { method: 'POST', body: fd });
    const data = await resp.json();

    const userPart = data.transcript.slice(fullTranscript.length).trim();
    if (userPart) {
      addMessage(userPart, 'user');
      fullTranscript = data.transcript;
    }

    if (data.question) {
      addMessage(data.question, 'bot');
    }
    if (data.message) {
      addMessage(data.message, 'bot');
    }
    if (data.audio) {
      new Audio(`data:audio/mpeg;base64,${data.audio}`).play();
    }
    if (data.done && data.log_dir) {
      pdfFrame.src = '/' + data.log_dir + '/invoice.pdf';
      pdfFrame.classList.remove('hidden');
    }
    status.textContent = '';
  }
});

