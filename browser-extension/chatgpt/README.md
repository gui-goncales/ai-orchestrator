# ChatGPT no Chrome normal

Esta extensão local conecta uma aba escolhida do ChatGPT ao AI Orchestrator.
Não usa Codex, API key, cookies exportados ou depuração remota. O login é feito
pelo próprio usuário no Chrome normal. Ela não corrige nem contorna bloqueios do Google.

## Instalar e conectar

1. Abra `chrome://extensions` no Chrome normal e ative Modo do desenvolvedor.
2. Use **Carregar sem compactação** e selecione esta pasta (`browser-extension/chatgpt`).
3. Abra `https://chatgpt.com`, entre normalmente e escolha o modelo GPT no site.
4. Clique na extensão **AI Orchestrator · ChatGPT** e depois em **Conectar esta aba**.
5. Copie o ID exibido. Em **Agents → ChatGPT → Gerenciar → Ajustar conexão**,
   cole em **ID da extensão ChatGPT**, salve e use **Já entrei, verificar**.
6. Mantenha o orquestrador aberto em `http://127.0.0.1:8787` no mesmo Chrome.
   Uma PWA instalada nesse Chrome também pode receber a ponte.

A extensão só aceita pedidos da origem local acima e só opera a aba ChatGPT escolhida.
As permissões permitem injetar o controle de interface em chatgpt.com, ler a resposta e
preencher/enviar pedidos. Ela não acessa senhas nem cookies. Não opera páginas de login.
Remover a extensão ou fechar a aba interrompe a disponibilidade; nenhum outro provedor
é acionado silenciosamente para contornar isso.

## Limitações

- O usuário precisa instalar e autorizar a extensão; não está publicada na Chrome Web Store.
- Mudanças da interface do ChatGPT podem exigir ajustes nos seletores.
- Sessão e controles reconhecidos não provam que uma geração foi bem-sucedida.
- Cancelar o backend encerra a espera local; confira a aba antes de reenviar.
- Não navegue para outra conversa durante a execução. A integração usa a conversa escolhida.
- O modelo é escolhido no ChatGPT e os limites dependem da conta. Tokens não são estimados como consumo real.
