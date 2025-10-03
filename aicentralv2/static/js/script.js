// Cadastrar novo usuário via API
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('form-usuario');

    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();

            const nome = document.getElementById('nome').value;
            const email = document.getElementById('email').value;

            try {
                const response = await fetch('/api/usuarios', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ nome, email })
                });

                if (response.ok) {
                    alert('Usuário cadastrado com sucesso!');
                    location.reload();
                } else {
                    alert('Erro ao cadastrar usuário');
                }
            } catch (error) {
                console.error('Erro:', error);
                alert('Erro ao cadastrar usuário');
            }
        });
    }
});