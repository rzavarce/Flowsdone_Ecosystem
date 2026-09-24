// Flowsdone landing page: mobile menu, reveal on scroll and the contact form
// (POST /public/contact on the gateway). No dependencies.
(function () {
  'use strict';
  document.documentElement.classList.add('js');

  // Mobile menu
  var toggle = document.querySelector('[data-nav-toggle]');
  var mobileNav = document.querySelector('[data-mobile-nav]');
  function setMenu(open) {
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Cerrar el menú' : 'Abrir el menú');
    mobileNav.hidden = !open;
  }
  if (toggle && mobileNav) {
    toggle.addEventListener('click', function () { setMenu(mobileNav.hidden); });
    mobileNav.addEventListener('click', function (e) { if (e.target.closest('a')) setMenu(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !mobileNav.hidden) { setMenu(false); toggle.focus(); } });
  }

  // Reveal on scroll
  var revealed = document.querySelectorAll('.section-head, .card, .steps li, .channel-grid li, .trust-list li, .faq details');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { entry.target.classList.add('visible'); io.unobserve(entry.target); }
      });
    }, { rootMargin: '0px 0px -8% 0px' });
    revealed.forEach(function (el) { el.classList.add('reveal'); io.observe(el); });
  }

  var year = document.querySelector('[data-year]');
  if (year) year.textContent = String(new Date().getFullYear());

  // Contact form
  var form = document.querySelector('[data-contact-form]');
  if (!form) return;
  var status = form.querySelector('[data-status]');
  var submit = form.querySelector('[data-submit]');
  var interest = form.querySelector('#c-interest');
  var message = form.querySelector('#c-message');

  // "Elegir Pro", "A medida"…: preselect "Planes y precios" and mention the plan.
  document.querySelectorAll('[data-plan]').forEach(function (link) {
    link.addEventListener('click', function () {
      interest.value = 'plans';
      if (!message.value.trim()) message.value = 'Me interesa el plan ' + link.getAttribute('data-plan') + '. ';
    });
  });

  var ERRORS = {
    name: 'Escribe tu nombre.',
    email: 'Escribe un email válido.',
    message: 'Cuéntanos un poco más (al menos 10 caracteres).',
    consent: 'Necesitamos tu permiso para responderte.'
  };

  function setError(field, text) {
    var input = form.elements[field];
    var holder = input.closest('.field') || input.closest('.consent');
    var existing = holder.querySelector('.field-error');
    if (existing) existing.remove();
    input.removeAttribute('aria-invalid');
    input.removeAttribute('aria-describedby');
    if (!text) return;
    var error = document.createElement('p');
    error.className = 'field-error';
    error.id = 'err-' + field;
    error.textContent = text;
    holder.appendChild(error);
    input.setAttribute('aria-invalid', 'true');
    input.setAttribute('aria-describedby', error.id);
  }

  function validate() {
    var data = new FormData(form);
    var problems = {};
    if (String(data.get('name') || '').trim().length < 2) problems.name = ERRORS.name;
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(data.get('email') || '').trim())) problems.email = ERRORS.email;
    if (String(data.get('message') || '').trim().length < 10) problems.message = ERRORS.message;
    if (!form.elements.consent.checked) problems.consent = ERRORS.consent;
    ['name', 'email', 'message', 'consent'].forEach(function (f) { setError(f, problems[f]); });
    var first = Object.keys(problems)[0];
    if (first) form.elements[first].focus();
    return !first;
  }

  function show(text, kind) {
    status.textContent = text;
    status.className = 'form-status' + (kind ? ' ' + kind : '');
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    show('');
    if (!validate()) return;
    var data = new FormData(form);
    var body = {
      name: String(data.get('name')).trim(),
      email: String(data.get('email')).trim(),
      company: String(data.get('company') || '').trim() || null,
      phone: String(data.get('phone') || '').trim() || null,
      interest: String(data.get('interest')),
      message: String(data.get('message')).trim(),
      website: String(data.get('website') || '')
    };
    submit.disabled = true;
    submit.textContent = 'Enviando…';
    fetch('/public/contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (response) {
      if (response.ok) {
        form.reset();
        show('¡Gracias! Hemos recibido tu mensaje y te responderemos por email muy pronto.', 'ok');
      } else if (response.status === 429) {
        show('Has enviado varios mensajes seguidos. Inténtalo de nuevo más tarde.', 'error');
      } else if (response.status === 422) {
        show('Revisa los datos del formulario e inténtalo de nuevo.', 'error');
      } else {
        show('No hemos podido enviar tu mensaje. Inténtalo de nuevo en unos minutos.', 'error');
      }
    }).catch(function () {
      show('No hay conexión. Comprueba tu red e inténtalo de nuevo.', 'error');
    }).then(function () {
      submit.disabled = false;
      submit.textContent = 'Enviar mensaje';
    });
  });
})();
