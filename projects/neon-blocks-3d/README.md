
# NEON BLOCKS 3D

Jogo arcade de blocos com lógica 2D e renderização 3D usando Three.js e Vite.

## Executar

```bash
npm install
npm run dev
```

Abra o endereço local indicado pelo Vite.

## Testes e build

```bash
npm test
npm run build
npm run preview
```

## Controles

- Setas esquerda/direita: mover
- Seta para cima ou X: girar no sentido horário
- Z: girar no sentido anti-horário
- Seta para baixo: acelerar descida
- Espaço: queda instantânea
- C ou Shift: guardar/trocar peça
- P ou Esc: pausar
- Enter: iniciar/retomar

No celular, use os botões na tela ou gestos sobre o tabuleiro.

## Estado de implementação

Primeira versão jogável com tabuleiro 10×20 visível, área oculta, 7-bag, hold, cinco próximas peças, ghost, SRS, gravidade, lock delay, pontuação, combos, T-spin básico, áudio sintetizado e recorde local.

Pendente antes de publicação: testes E2E no navegador, revisão de acessibilidade, PWA offline, TypeScript/React/Zustand, otimização do bundle e QA de dispositivos móveis.
