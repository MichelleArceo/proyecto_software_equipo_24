const API_BASE = 'http://localhost:8000'; 

document.getElementById('message-form').addEventListener('submit', function(e) {
    e.preventDefault(); 
    
    const userInput = document.getElementById('user-input');
    const messageText = userInput.value.trim();
    
    if (messageText === "") {
        return;
    }

    // 1. Mostrar el mensaje del usuario
    appendMessage(messageText, 'user');
    
    // 2. Limpiar el área de entrada
    userInput.value = '';

    // 3. Obtener la respuesta del bot desde el backend
    getBotResponseFromBackend(messageText);
});

// ... [Función appendMessage sigue igual] ...
function appendMessage(text, sender) {
    const chatHistory = document.getElementById('chat-history');
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);
    messageDiv.textContent = text;
    chatHistory.appendChild(messageDiv);
    
    // Desplazar hacia abajo automáticamente
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return messageDiv;
}


// NUEVA FUNCIÓN: Envía el mensaje al backend y procesa la respuesta.
async function getBotResponseFromBackend(message) {
      // pinta loading
  let loadingMessage = appendMessage("...", 'bot');

  try {
    // 1) ahora pegamos al GATEWAY (encadena intención → segundo endpoint)
    const res = await fetch(`${API_BASE}/gateway`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ utterance: message, tipo_busqueda: "texto" })
    });

    // quita loading
    const chatHistory = document.getElementById('chat-history');
    if (loadingMessage && chatHistory.contains(loadingMessage)) {
      chatHistory.removeChild(loadingMessage);
    }

    if (!res.ok) {
      const errText = await res.text();
      appendMessage(`❌ Error: ${res.status} ${errText}`, 'bot');
      return;
    }

    const data = await res.json();

    // 2) Render: lista de recomendaciones si viene "detalles"
    if (Array.isArray(data.detalles) && data.detalles.length) {
      const lines = data.detalles.map((d, i) => {
        const t = d.pelicula?.titulo ?? '(sin título)';
        const r = d.razon_recomendacion ? ` — ${d.razon_recomendacion}` : '';
        return `${i + 1}. ${t}${r}`;
      });
      appendMessage(`🎬 Recomendaciones:\n${lines.join('\n')}`, 'bot');
      return;
    }

    // 3) Mensajes simples
    if (data.mensaje) {
      appendMessage(`✅ ${data.mensaje}`, 'bot');
      return;
    }

    // 4) Fallback
    appendMessage('🤖 No tengo resultados para mostrar.', 'bot');

  } catch (error) {
    // quita loading si sigue
    const chatHistory = document.getElementById('chat-history');
    if (loadingMessage && chatHistory.contains(loadingMessage)) {
      chatHistory.removeChild(loadingMessage);
    }
    appendMessage(`❌ Error de conexión: ${error.message}`, 'bot');
  }

}