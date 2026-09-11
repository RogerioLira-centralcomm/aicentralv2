(function () {
  'use strict';
  var badge = document.getElementById('cx-sign-count');
  if (!badge) return;
  fetch('/assinaturas/api/badge', { credentials: 'same-origin' })
    .then(function (response) { return response.json(); })
    .then(function (payload) {
      var count = payload && payload.data ? Number(payload.data.count || 0) : 0;
      if (!count) {
        badge.hidden = true;
        badge.textContent = '0';
        return;
      }
      badge.hidden = false;
      badge.textContent = count > 3 ? '3+' : String(count);
    })
    .catch(function () {});
})();
