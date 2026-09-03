/**
 * CentralX cx-drawer — off-canvas drawer reutilizável para o design system enterprise.
 *
 * Uso mínimo:
 *   var id = cxDrawer.open({
 *     title: 'Editar cliente',
 *     size: 'xl',            // 'sm' | 'md' | 'lg' | 'xl'  (xl = 75% da tela)
 *     breadcrumb: 'CRM v3 · Portal Auto Shopping',
 *     content: '<form>...</form>',
 *     actions: [
 *       { label: 'Cancelar', variant: 'ghost', close: true },
 *       { label: 'Salvar', variant: 'primary', onClick: submit }
 *     ],
 *     split: true,           // modo split: empurra o painel central ~40%
 *     nested: false,         // segundo drawer sobre o primeiro
 *     onOpen: fn, onClose: fn
 *   });
 *   cxDrawer.close(id);
 *
 * Segurança:
 * - Conteúdo em `content` NÃO é sanitizado; o chamador é responsável por escapar dados
 *   do usuário. Utilize `contentEl` para receber um HTMLElement ou DocumentFragment.
 */
(function (global) {
    'use strict';

    var openStack = [];
    var idCounter = 0;

    function ensureRoot() {
        var root = document.getElementById('cx-drawer-root');
        if (!root) {
            root = document.createElement('div');
            root.id = 'cx-drawer-root';
            document.body.appendChild(root);
        }
        return root;
    }

    function makeId() {
        idCounter += 1;
        return 'cx-drawer-' + Date.now() + '-' + idCounter;
    }

    function createDrawer(opts) {
        var id = opts.id || makeId();
        var wrap = document.createElement('div');
        wrap.className = 'cx-drawer-wrap';
        wrap.setAttribute('data-drawer-id', id);

        var isNested = openStack.length > 0 || opts.nested;
        var backdrop = document.createElement('div');
        backdrop.className = 'cx-drawer-backdrop' + (isNested ? ' is-nested' : '');
        backdrop.setAttribute('data-drawer-backdrop', id);

        var drawer = document.createElement('aside');
        drawer.className = 'cx-drawer';
        drawer.setAttribute('role', 'dialog');
        drawer.setAttribute('aria-modal', 'true');
        drawer.setAttribute('data-size', opts.size || 'md');
        drawer.setAttribute('data-nested', isNested ? 'true' : 'false');
        drawer.setAttribute('tabindex', '-1');
        drawer.id = id;

        // Header
        var header = document.createElement('div');
        header.className = 'cx-drawer-header';

        var titles = document.createElement('div');
        titles.className = 'cx-drawer-titles';

        if (opts.title) {
            var titleEl = document.createElement('div');
            titleEl.className = 'cx-drawer-title';
            titleEl.textContent = opts.title;
            titleEl.setAttribute('id', id + '-title');
            drawer.setAttribute('aria-labelledby', id + '-title');
            titles.appendChild(titleEl);
        }
        if (opts.breadcrumb) {
            var bc = document.createElement('div');
            bc.className = 'cx-drawer-breadcrumb';
            bc.textContent = opts.breadcrumb;
            titles.appendChild(bc);
        }
        header.appendChild(titles);

        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'cx-drawer-close';
        closeBtn.setAttribute('aria-label', 'Fechar');
        closeBtn.innerHTML = '<i class="fa-solid fa-xmark" aria-hidden="true"></i>';
        closeBtn.addEventListener('click', function () { close(id); });
        header.appendChild(closeBtn);

        drawer.appendChild(header);

        // Body
        var body = document.createElement('div');
        body.className = 'cx-drawer-body';
        if (opts.contentEl) {
            body.appendChild(opts.contentEl);
        } else if (typeof opts.content === 'string') {
            body.innerHTML = opts.content;
        }
        drawer.appendChild(body);

        // Footer com ações
        if (opts.actions && opts.actions.length) {
            var footer = document.createElement('div');
            footer.className = 'cx-drawer-footer';
            opts.actions.forEach(function (act) {
                var btn = document.createElement('button');
                btn.type = act.type || 'button';
                btn.className = actionClass(act.variant);
                btn.textContent = act.label || 'Ação';
                if (act.id) btn.id = act.id;
                if (act.disabled) btn.disabled = true;
                if (act.close) {
                    btn.addEventListener('click', function (ev) {
                        if (typeof act.onClick === 'function') act.onClick(ev, id);
                        close(id);
                    });
                } else if (typeof act.onClick === 'function') {
                    btn.addEventListener('click', function (ev) { act.onClick(ev, id); });
                }
                footer.appendChild(btn);
            });
            drawer.appendChild(footer);
        }

        // Backdrop click fecha (exceto se opts.persistent)
        if (!opts.persistent) {
            backdrop.addEventListener('click', function () { close(id); });
        }

        wrap.appendChild(backdrop);
        wrap.appendChild(drawer);
        ensureRoot().appendChild(wrap);

        // Registrar entry
        var entry = {
            id: id,
            wrap: wrap,
            drawer: drawer,
            backdrop: backdrop,
            body: body,
            opts: opts,
            split: !!opts.split,
            prevFocus: document.activeElement,
        };
        openStack.push(entry);

        // Split mode: apenas o primeiro drawer aplica; aninhados herdam.
        if (entry.split && openStack.filter(function (e) { return e.split; }).length === 1) {
            document.body.classList.add('cx-drawer-split-active');
        }

        // Trigger animation on next frame
        requestAnimationFrame(function () {
            backdrop.classList.add('is-open');
            drawer.classList.add('is-open');
            drawer.focus();
            if (typeof opts.onOpen === 'function') opts.onOpen(id, drawer);
        });

        // Escape para fechar o topo da pilha
        if (openStack.length === 1) bindGlobalKey();

        return id;
    }

    function actionClass(variant) {
        switch (variant) {
            case 'primary': return 'btn btn-sm btn-primary';
            case 'danger': return 'btn btn-sm btn-error';
            case 'ghost': return 'btn btn-sm btn-ghost';
            case 'outline': return 'btn btn-sm btn-outline';
            default: return 'btn btn-sm';
        }
    }

    function _keyHandler(ev) {
        if (ev.key === 'Escape' && openStack.length) {
            var top = openStack[openStack.length - 1];
            if (top && !top.opts.persistent) close(top.id);
        }
    }
    function bindGlobalKey() {
        document.addEventListener('keydown', _keyHandler);
    }
    function unbindGlobalKey() {
        document.removeEventListener('keydown', _keyHandler);
    }

    function close(id) {
        var idx = -1;
        for (var i = openStack.length - 1; i >= 0; i--) {
            if (openStack[i].id === id) { idx = i; break; }
        }
        if (idx === -1) return;
        var entry = openStack[idx];
        entry.drawer.classList.remove('is-open');
        entry.backdrop.classList.remove('is-open');
        setTimeout(function () {
            if (entry.wrap.parentNode) entry.wrap.parentNode.removeChild(entry.wrap);
            openStack.splice(idx, 1);
            if (entry.split && !openStack.some(function (e) { return e.split; })) {
                document.body.classList.remove('cx-drawer-split-active');
            }
            if (!openStack.length) unbindGlobalKey();
            if (entry.prevFocus && typeof entry.prevFocus.focus === 'function') {
                try { entry.prevFocus.focus(); } catch (_) { /* ignore */ }
            }
            if (typeof entry.opts.onClose === 'function') entry.opts.onClose(id);
        }, 220);
    }

    function closeAll() {
        openStack.slice().forEach(function (entry) { close(entry.id); });
    }

    function getBody(id) {
        var entry = openStack.find(function (e) { return e.id === id; });
        return entry ? entry.body : null;
    }
    function isOpen(id) {
        return openStack.some(function (e) { return e.id === id; });
    }
    function top() {
        return openStack.length ? openStack[openStack.length - 1] : null;
    }

    global.cxDrawer = {
        open: createDrawer,
        close: close,
        closeAll: closeAll,
        getBody: getBody,
        isOpen: isOpen,
        top: top,
    };
})(window);
