# Prompts para usar o Agentic Video Editor

Os exemplos abaixo podem ser adaptados a qualquer idioma, estilo e pasta de trabalho. Substitua as partes entre colchetes pelo contexto do projeto e anexe as mídias quando necessário.

## Instalar a skill no Codex

```text
Use $skill-installer para instalar esta skill:
https://github.com/TramontaG/AgenticVideoEditor/tree/main/skills/video-edit
```

Para outro agente que suporte Agent Skills:

```text
Instale a skill disponível na pasta skills/video-edit deste repositório:
https://github.com/TramontaG/AgenticVideoEditor

Inclua o SKILL.md, os scripts, as referências e os templates da pasta assets.
Siga as convenções de instalação de skills do seu agente.
```

## Preparar um computador

```text
Use $video-edit para preparar este computador para edição de vídeos.
Detecte o sistema operacional, confira o que já está instalado e prepare as
dependências ausentes em um ambiente isolado. Use [pasta escolhida] para os
projetos e modelos; se eu não indicar uma pasta, use o padrão da skill.

Verifique CPU, memória, espaço e GPU. Use processamento por CPU quando não
houver aceleração compatível. Baixe os modelos auxiliares iniciais, execute
o teste completo e me informe o que foi validado e o que ainda falta.
```

## Editar mídias fornecidas

```text
Use $video-edit para montar um vídeo sobre [assunto] com as mídias anexadas.
O objetivo é [objetivo], o público é [público] e a duração aproximada é [duração].
Exporte em [16:9 ou 9:16], [HD, FHD ou QHD], com [idioma e estilo de legenda].

Analise o conteúdo e as cenas, escolha os melhores trechos e decida a ordem,
o enquadramento e o ritmo. Crie gráficos ou diagramas no Motion Canvas quando
ajudarem a explicar o assunto. Mantenha a timeline completa no Remotion e
preserve os assets e as fontes para revisões posteriores.

Não inclua stock assets sem minha autorização. Entregue uma prévia e a
exportação final com o projeto editável.
```

## Recortar uma pessoa, trocar o fundo e reduzir pausas

```text
Use $video-edit neste vídeo e na imagem de fundo anexada.
Remova o fundo do vídeo, coloque a imagem como cenário e corte pausas longas,
preservando uma margem natural antes e depois de cada fala.

Verifique o recorte em cabelo, mãos e movimentos. Se a máscara ficar instável,
teste um trecho representativo antes de processar o vídeo inteiro e escolha
uma abordagem adequada ao hardware. Não altere os originais.

Gere legendas com o tempo ajustado aos cortes e mantenha o recorte, o fundo e
a timeline separados. Se esse fluxo se tornar recorrente, salve um script
parametrizado e documente como reutilizá-lo.
```

## Revisar um projeto existente

```text
Use $video-edit no projeto [nome ou caminho].
Troque o gráfico em [tempo] por [alteração] e ajuste a legenda de [trecho].
Consulte a timeline existente, salve uma revisão e reutilize os assets que
continuarem válidos. Atualize os elementos dependentes e exporte uma nova
versão sem sobrescrever a anterior.
```

## Adaptar para outra orientação

```text
Use $video-edit para criar uma versão [9:16 ou 16:9] do projeto [projeto].
Reenquadre cada cena, ajuste títulos, legendas e gráficos à nova composição
e preserve o foco visual. Mantenha a versão anterior disponível e exporte
a nova em [resolução].
```

## Registrar um estilo de edição

```text
Use $video-edit para analisar estas referências de edição: [referências].
Descreva tipografia, cores, ritmo, transições, legendas e tratamento de áudio.
Separe o que é observado do que é inferido e salve um perfil chamado [nome].

Use esse perfil no projeto [projeto]. Registre meus ajustes no perfil quando
eu indicar que são preferências permanentes; trate as outras correções como
decisões específicas deste vídeo.
```

## Criar uma animação reutilizável

```text
Use $video-edit para criar no Motion Canvas uma animação de [gráfico ou diagrama]
para explicar [conceito], com duração de [duração]. Use os dados [dados] e o
perfil visual [perfil].

Salve o código e a renderização em pastas separadas, preserve transparência
quando necessária e integre o asset à timeline do projeto [projeto] no Remotion.
```

## Buscar stock sem autorizar inclusão

```text
Use $video-edit para procurar no Pexels opções de [tipo de cena].
Mostre os candidatos e indique em qual trecho cada um ajudaria. Esta mensagem
autoriza apenas a busca; aguarde minha escolha antes de incluir qualquer asset.
Se faltar a chave da API, oriente-me a configurá-la por um método privado.
```

## Conceder autonomia limitada para stock

Use apenas se quiser conceder essa autonomia:

```text
No projeto [projeto], autorizo a seleção e inclusão de assets do Pexels sobre
[temas permitidos], com no máximo [quantidade] assets. Registre a origem e
essa autorização. Para outros temas ou projetos, consulte-me novamente.
```
