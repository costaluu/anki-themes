# anki-themes

Extensão do Anki que troca o tema de cores do aplicativo inteiro (janelas, menus, baralhos, revisão,
navegador, editor). Cada tema é um arquivo JSON; o primeiro é o **Flame**.

## Temas

| id | Nome | Descrição |
|---|---|---|
| `flame` | Flame | Fundo de brasa (escuro) ou creme quente (claro), acentos do amarelo ao vinho. Inspirado no tema Flame do Review Heatmap (escala YlOrRd do ColorBrewer). |

Claro ou escuro segue a preferência do próprio Anki (Ferramentas → Preferências → Aparência); o tema define as duas variantes.

## Instalar (Linux)

```sh
git clone <este-repo> anki-themes && cd anki-themes
./install.py --dry-run     # mostra o que será feito
./install.py               # instala no Flatpak e/ou em ~/.local/share/Anki2
```
Feche o Anki antes e abra de novo depois. Opções: `--list`, `--target flatpak|native`, `--dest PASTA_addons21`,
`--link` (symlink, para desenvolver), `--uninstall`. A versão anterior vai para
`~/.local/share/anki-addons-backups/<data>/` (nunca para dentro de `addons21`).

## Usar
Ferramentas → **Temas** → escolha um tema, ou "Padrão do Anki" para desligar. A escolha fica no `config.json`
da extensão (`"theme": "flame"`). Janelas já abertas (navegador, editor) mostram o tema novo ao reabrir.

## Como funciona
O Anki gera a paleta do Qt e todas as páginas web a partir da mesma tabela de 51 cores (`_aqt/colors.py`), e as
páginas usam variáveis CSS com os mesmos nomes (`--canvas`, `--fg`...).
- **Qt:** a extensão sobrescreve os valores dessa tabela antes de o Anki montar a paleta e refaz o estilo
  (`theme_manager.apply_style`). Os originais são guardados e restaurados ao desligar.
- **Web:** injeta um `<style>` que redefine as variáveis em `html:root` (claro) e `html:root.night-mode` (escuro),
  com especificidade maior que a do Anki. Páginas carregadas por fora (estatísticas) recebem o estilo via
  `webview_did_inject_style_into_page`.
- Bandeiras (`flag-*`) e os estados enterrado/marcado/suspenso **não** são alterados de propósito: a cor deles
  carrega significado.

## Criar um tema novo
Copie `addon/themes/flame.json` para `addon/themes/<id>.json` e mude as cores. Formato:

```json
{ "id": "meu-tema", "name": "Meu tema", "description": "...",
  "tokens": { "light": { "canvas": "#fff" }, "dark": { "canvas": "#000" } },
  "extra_css": "", "extra_qss": "" }
```
- Nomes dos tokens = variáveis CSS do Anki sem `--` (lista completa em `_aqt/colors.py`).
- Valores: só cores (`#hex`, nomes, `rgb()/rgba()/hsl()/hsla()`). `extra_css`/`extra_qss` não podem conter `</`,
  `@import`, `url(` nem `javascript:`; um arquivo inválido é ignorado e registrado no stderr, sem afetar os outros.
- Pode definir só `light` ou só `dark`.

## Testes
```sh
python3 -I -m unittest discover -s tests -v
```
`test_engine.py` cobre validação, geração de CSS e aplicação/restauração das cores; `test_wiring.py` carrega a
extensão contra um `aqt` simulado. Fora isso, o Flame foi validado contra a tabela de cores real do Anki 26.09.3
(todos os 41 tokens existem) e renderizado com o CSS real do Anki, em claro e escuro.

## Limites conhecidos
- Não testado ainda com a interface do Anki aberta; a primeira abertura real é o teste final.
- O reaplicar ao vivo usa atributos internos do Anki (`theme_manager._current_widget_style`); se falhar, reiniciar
  o Anki sempre aplica.
- Cartões com CSS próprio no tipo de nota que fixe cores (sem usar variáveis) não mudam.
