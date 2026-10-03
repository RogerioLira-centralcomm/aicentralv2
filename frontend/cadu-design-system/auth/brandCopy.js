// Words of the access screens per product. The server sends bootstrap.product ('centralx' on the internal
// CentralX host, otherwise 'cadu'); nothing on a CentralX screen may say "Cadu".
const COPY = {
  cadu: {
    loginTitle: 'Continue seu trabalho no Cadu',
    loginDescription: 'Entre para retomar projetos, fontes, decisões e entregas.',
    loginDivider: 'ou entre com email',
    visualKicker: 'Cadu Workspace',
    visualText: 'Retome o trabalho com o contexto por perto.',
    transitionTitle: 'Entrando no Cadu Workspace',
    transitionText: 'Preparando seu espaço de trabalho…',
    forgotDescription: 'Informe seu email e enviaremos um link para redefinir sua senha.',
    forgotLabel: 'Email de trabalho',
    forgotPlaceholder: 'nome@empresa.com',
  },
  centralx: {
    loginTitle: 'Acesse o CentralX',
    loginDescription: 'Use seu acesso @centralcomm.media para entrar.',
    loginDivider: 'ou entre com seu usuário',
    visualKicker: 'CentralX',
    visualText: 'O acesso interno da CentralComm.',
    transitionTitle: 'Entrando no CentralX',
    transitionText: 'Preparando seu ambiente…',
    forgotDescription: 'Informe seu email @centralcomm.media e enviaremos um link para redefinir sua senha.',
    forgotLabel: 'Email corporativo',
    forgotPlaceholder: 'nome@centralcomm.media',
  },
};

export const copyFor = bootstrap => COPY[bootstrap?.product] || COPY.cadu;
