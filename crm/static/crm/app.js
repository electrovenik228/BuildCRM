function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return '';
}

function formatCurrency(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return '$0';
  return `$${amount.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

function setupApartmentModal() {
  const modal = document.getElementById('apartment-modal');
  if (!modal) return;

  const fields = {
    number: document.getElementById('modal-number'),
    floor: document.getElementById('modal-floor'),
    rooms: document.getElementById('modal-rooms'),
    area: document.getElementById('modal-area'),
    price: document.getElementById('modal-price'),
    status: document.getElementById('modal-status'),
    payment: document.getElementById('modal-payment'),
  };

  document.querySelectorAll('.apartment-card').forEach((card) => {
    card.addEventListener('click', () => {
      fields.number.textContent = `Квартира ${card.dataset.number}`;
      fields.floor.textContent = card.dataset.floor;
      fields.rooms.textContent = card.dataset.rooms;
      fields.area.textContent = card.dataset.area;
      fields.price.textContent = formatCurrency(card.dataset.price);
      fields.status.textContent = card.dataset.status;
      fields.payment.textContent = card.dataset.payment;
      modal.hidden = false;
    });
  });

  modal.querySelectorAll('[data-close-modal]').forEach((el) => {
    el.addEventListener('click', () => {
      modal.hidden = true;
    });
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') modal.hidden = true;
  });
}

function setupChat() {
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const log = document.getElementById('chat-log');
  if (!form || !input || !log) return;

  function addMessage(role, text) {
    const item = document.createElement('div');
    item.className = `chat-message ${role}`;
    item.textContent = text;
    log.appendChild(item);
    log.scrollTop = log.scrollHeight;
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    addMessage('user', message);
    input.value = '';

    try {
      const response = await fetch('/api/ai/chat/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify({ message }),
      });
      const payload = await response.json();
      addMessage('assistant', payload.answer || 'Не удалось получить ответ.');
    } catch (error) {
      addMessage('assistant', 'Ошибка соединения с AI endpoint.');
    }
  });
}

setupApartmentModal();
setupChat();
