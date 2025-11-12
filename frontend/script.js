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
    messageDiv.innerHTML = text;
    chatHistory.appendChild(messageDiv);
    
    // Desplazar hacia abajo automáticamente
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return messageDiv;
}


// NUEVA FUNCIÓN: Envía el mensaje al backend y procesa la respuesta.
async function getBotResponseFromBackend(message) {
  // Mostrar mensaje de carga
  let loadingMessage = appendMessage("...", 'bot');

  try {
    const res = await fetch(`${API_BASE}/gateway`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ utterance: message, tipo_busqueda: "texto" })
    });

    // Quitar mensaje de carga
    const chatHistory = document.getElementById('chat-history');
    if (loadingMessage && chatHistory.contains(loadingMessage)) {
      chatHistory.removeChild(loadingMessage);
    }

    if (!res.ok) {
      const errText = await res.text();
      const httpCode = res.status;
      if (httpCode != 422) {
        appendMessage(`❌ Error: ${res.status} ${errText}`, 'bot');
      } else {
        appendMessage("❌ Esta operación no está implementada, por favor intenta de nuevo.", 'bot');
      }
      return;
    }

    const data = await res.json();

    // 🔹 Caso 1: Respuesta con lista de recomendaciones
    if (Array.isArray(data.detalles) && data.detalles.length) {
      const rows = data.detalles.map((d, i) => {
        const titulo = d.pelicula?.titulo ?? '(sin título)';
        const razon = d.razon_recomendacion ?? '';
        const evalNum = typeof d.evaluacion === 'number' ? d.evaluacion : null;

        // Generar estrellas
        let estrellasHTML = '';
        if (evalNum !== null) {
          const maxStars = 5;
          for (let s = 1; s <= maxStars; s++) {
            estrellasHTML += s <= evalNum
              ? '<span style="color: gold; font-size: 1.2em;">★</span>'
              : '<span style="color: #ccc; font-size: 1.2em;">☆</span>';
          }
        }

        return `
          <tr>
            <td style="padding: 4px 8px; vertical-align: top;">
              <strong>${i + 1}. ${titulo}</strong><br>
              ${evalNum !== null ? `<div>${estrellasHTML}</div>` : ''}
            </td>
            <td style="padding: 4px 8px; vertical-align: top;">${razon}</td>
          </tr>
        `;
      }).join('');

      const tableHTML = `
        <div>
          <p>🎬 <strong>Recomendaciones:</strong></p>
          <table style="border-collapse: collapse; width: 100%; margin-top: 6px;">
            <thead>
              <tr>
                <th style="text-align: left; padding: 4px 8px;">Película</th>
                <th style="text-align: left; padding: 4px 8px;">Motivo</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      `;
      appendMessage(tableHTML, 'bot');
      return;
    }

    // 🔹 Caso 2: Sin recomendaciones pendientes (mensaje especial)
    if (data.mensaje && data.mensaje.includes("No hay recomendaciones pendientes")) {
      appendMessage("🎉 ¡Has terminado de evaluar todas las recomendaciones! Gracias por tu participación. 🙌", 'bot');
      return;
    }

    // 🔹 Caso 3: Evaluación pendiente (intención calificar_recomendaciones)
    if (data.mensaje && data.mensaje.includes("Evaluación pendiente") && data.detalle) {
      const d = data.detalle;
      const peli = d.pelicula ?? {};
      const buttons = [0, 1, 2, 3, 4, 5]
        .map(n => `<button class="rating-btn" data-id="${d.objectId}" data-score="${n}">${n}</button>`)
        .join('') + `<button class="rating-btn" data-score="exit">Salir</button>`;

      const html = `
        <div class="rating-block">
          <p>🎬 <strong>${peli.titulo}</strong></p>
          <p>${peli.sinopsis ?? '(Sin sinopsis disponible)'}<br>
          💡 <em>${d.razon_recomendacion ?? ''}</em></p>
          <p><strong>Evalúa esta recomendación:</strong></p>
          <div>${buttons}</div>
        </div>
      `;

      const msgDiv = appendMessage(html, 'bot');

      // Agregar listeners a los botones
      msgDiv.querySelectorAll('.rating-btn').forEach(btn => {
        btn.addEventListener('click', async (ev) => {
          const score = ev.target.dataset.score;
          if (score === 'exit') {
            appendMessage("Gracias por tus evaluaciones 😊", 'bot');
            return;
          }
          const id = ev.target.dataset.id;
          await fetch(`${API_BASE}/evaluar/${id}?evaluacion=${score}`, { method: "PATCH" });
          appendMessage(`⭐ Evaluación registrada (${score} estrellas).`, 'bot');
          // Mostrar siguiente
          getBotResponseFromBackend("quiero calificar las recomendaciones");
        });
      });
      return;
    }

    // 🔹 Caso 4: Mensajes simples
    if (data.mensaje) {
      appendMessage(`✅ ${data.mensaje}`, 'bot');
      return;
    }

    // 🔹 Fallback
    appendMessage('🤖 No tengo resultados para mostrar.', 'bot');

  } catch (error) {
    const chatHistory = document.getElementById('chat-history');
    if (loadingMessage && chatHistory.contains(loadingMessage)) {
      chatHistory.removeChild(loadingMessage);
    }
    appendMessage(`❌ Error de conexión: ${error.message}`, 'bot');
  }
}
