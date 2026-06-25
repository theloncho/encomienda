document.addEventListener('DOMContentLoaded', function () {

    // ── Inicializar tooltips de Bootstrap ─────────────────────
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(el => new bootstrap.Tooltip(el));
  
    // ── Auto-cerrar alertas flash despues de 5 segundos ───────
    // (complementa la animacion CSS del styles.css)
    setTimeout(function () {
      document.querySelectorAll('.alert').forEach(function (alert) {
        if (typeof bootstrap !== 'undefined' && bootstrap.Alert) {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }
      });
    }, 5000);
  
    // ── Confirmacion antes de eliminar ────────────────────────
    window.confirmar = function (mensaje) {
      return confirm(mensaje || '¿Estás seguro?');
    };
  
  });
  
  // ── Resaltar fila al hacer clic (navegacion intuitiva) ───────
  document.querySelectorAll('.fila-link').forEach(function (fila) {
    fila.addEventListener('click', function () {
      if (this.dataset.href) {
          window.location = this.dataset.href;
      }
    });
  });
