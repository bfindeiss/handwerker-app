
document.addEventListener('DOMContentLoaded', () => {
  const recordBtn = document.getElementById('record');
  const status = document.getElementById('status');
  const chat = document.getElementById('chat');
  const pdfFrame = document.getElementById('pdfViewer');
  const helpToggle = document.getElementById('helpToggle');
  const helpPanel = document.getElementById('helpPanel');
  const textInput = document.getElementById('textInput');
  const sendText = document.getElementById('sendText');

  const sessionId = crypto.randomUUID();
  let recorder;
  let audioStream;
  let fullTranscript = '';
  let pendingClarifications = [];

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

  if (helpToggle && helpPanel) {
    helpToggle.addEventListener('click', () => {
      helpPanel.classList.toggle('hidden');
    });
  }

  if (sendText && textInput) {
    sendText.addEventListener('click', (e) => {
      e.preventDefault();
      sendTextMessage();
    });
    textInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        sendTextMessage();
      }
    });
  }

  async function sendAudio(blob) {
    const fd = new FormData();
    fd.append('session_id', sessionId);
    fd.append('file', blob, 'audio.wav');
    if (pendingClarifications.length) {
      fd.append('clarification_context', pendingClarifications.join(' | '));
      pendingClarifications = [];
    }
    const resp = await fetch('/conversation/', { method: 'POST', body: fd });
    const data = await resp.json();

    const userPart = data.transcript.slice(fullTranscript.length).trim();
    if (userPart) {
      addMessage(userPart, 'user');
      fullTranscript = data.transcript;
    }

    if (Array.isArray(data.clarification_questions) && data.clarification_questions.length) {
      pendingClarifications = data.clarification_questions;
      data.clarification_questions.forEach((question) => addMessage(question, 'bot'));
    } else if (data.question) {
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

  async function sendTextMessage() {
    const text = textInput.value.trim();
    if (!text) return;
    addMessage(text, 'user');
    textInput.value = '';
    status.textContent = 'Verarbeite...';
    const fd = new FormData();
    fd.append('session_id', sessionId);
    fd.append('text', text);
    if (pendingClarifications.length) {
      fd.append('clarification_context', pendingClarifications.join(' | '));
      pendingClarifications = [];
    }
    const resp = await fetch('/conversation-text/', { method: 'POST', body: fd });
    const data = await resp.json();

    fullTranscript = data.transcript;
    if (Array.isArray(data.clarification_questions) && data.clarification_questions.length) {
      pendingClarifications = data.clarification_questions;
      data.clarification_questions.forEach((question) => addMessage(question, 'bot'));
    } else if (data.question) {
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
