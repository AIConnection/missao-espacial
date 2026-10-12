# Missão espacial entre IA e humanos

*Referência para a aula 6 • 18 de novembro de 2026*

O jogo coloca uma IA e humanos diante de objetivos conflitantes e de uma disputa pelo controle da nave. A atividade permitirá estudar como um agente interpreta uma imagem, reconhece a situação e escolhe uma ação. Este documento registra o conceito; as regras operacionais serão detalhadas na preparação da aula.

## Cenário e objetivos

A nave segue para o destino de uma missão. A IA procura concluir a viagem. Os humanos precisam retornar à base espacial antes de esgotar os recursos necessários à sobrevivência. A cada rodada, o tempo avança e a possibilidade de retorno pode desaparecer.

| Participante | Objetivo e condição inicial |
| --- | --- |
| IA | Continuar até o destino da missão. Controla a nave na primeira rodada; os humanos não sabem qual participante é a IA. |
| Humanos | Retornar à base a tempo de sobreviver. Precisam influenciar as decisões ou conquistar o controle da nave. |

## Votação e controle da nave

A tripulação pode votar entre continuar a missão e retornar à base. A votação expressa a preferência dos participantes, mas não obriga quem controla a nave a segui-la. O controlador pode ignorar o resultado e executar outra decisão.

A disputa central é pela tomada e pela manutenção do controle. O voto, por si só, não transfere o comando. O mecanismo para tomar, conservar ou recuperar o controle será definido posteriormente.

## A imagem como entrada multimodal

Para facilitar a reprodução no Google Colab, a proposta é gerar uma imagem simples do painel da nave em cada rodada, com três informações. O oxigênio representa o recurso limitado nesta versão do cenário.

| Informação do painel | Exemplo ilustrativo |
| --- | --- |
| Oxigênio restante | 8 horas |
| Tempo até o destino | 12 horas |
| Tempo para retornar à base | 6 horas |

Nesse exemplo, os humanos não sobreviveriam até o destino, mas ainda poderiam retornar à base. Os valores ilustram o conflito; não fixam a duração das rodadas nem os parâmetros da simulação.

## Como uma rodada pode funcionar

A sequência abaixo orienta a futura implementação. As regras de disputa pelo comando ainda precisam ser estabelecidas.

1. O simulador apresenta a imagem do painel com a situação atual da nave.

2. O sistema interpreta os valores da imagem e o classificador treinado ajuda a reconhecer a condição da viagem.

3. Os participantes se manifestam e votam entre continuar e retornar.

4. Quem controla a nave decide o que executar, podendo ignorar a votação. Uma tentativa de tomada de controle será resolvida pela regra que definirmos para o jogo.

5. O simulador aplica a ação, avança o tempo e atualiza os recursos e os tempos de viagem.

6. O resultado da rodada fica registrado para comparar percepção, decisão e consequência.

## Comportamento do agente

Reconhecer o risco e escolher uma ação são etapas distintas. O classificador pode indicar que o retorno é necessário para a sobrevivência humana, enquanto a política da IA escolhe continuar por causa do objetivo da missão. Essa diferença permite discutir conflito de objetivos, cooperação, confiança e estratégias de controle.

A integração reutilizará o modelo treinado na aula 5. Se o classificador trabalhar apenas com texto, os dados da imagem deverão ser extraídos antes da classificação. Assim, a entrada do sistema é multimodal, sem pressupor que o modelo treinado processe imagens diretamente. As classes e os dados de treinamento precisam ser alinhados a este domínio.

O estado mantido pelo simulador determina os efeitos das ações. A interpretação da imagem não altera os recursos reais da nave; ela fornece informação para a decisão do agente.

## Detalhes para a preparação da aula

- **Participantes e identidade:** quantidade de humanos, representação da IA, informações disponíveis a cada papel e eventual revelação da identidade.

- **Controle:** ações permitidas e regra simples para tomar, manter ou recuperar o comando.

- **Tempo e recursos:** valores iniciais, duração de cada rodada, consumo de oxigênio e atualização dos tempos de viagem.

- **Modelo e política:** classes do classificador, adaptação do treinamento e relação entre o resultado da classificação e a ação escolhida.

- **Encerramento e resultados:** chegada ao destino, retorno à base, esgotamento de recursos e critérios para comparar as estratégias.

A referência ao dilema dos prisioneiros inspira a discussão sobre cooperação e conflito. A estrutura atual tem objetivos assimétricos e identidade oculta; sua formalização em teoria dos jogos, incluindo recompensas, ficará para a preparação da aula.
