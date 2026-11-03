# anki-themes

Extensão do Anki que troca o tema de cores do aplicativo inteiro (janelas, menus, baralhos, revisão,
navegador, editor). Cada tema é um arquivo JSON; o primeiro é o **Flame**.

## Temas

| id | Nome | Claro / Escuro |
|---|---|---|
| `flame` | Flame | creme quente / brasa. Escala YlOrRd, inspirada no tema Flame do Review Heatmap. |
| `catppuccin` | Catppuccin Mocha | Latte / Mocha (o mesmo do terminal) |
| `catppuccin-macchiato` | Catppuccin Macchiato | Latte / Macchiato |
| `catppuccin-frappe` | Catppuccin Frappé | Latte / Frappé |
| `gruvbox` | Gruvbox | creme e marrom / grafite quente |

Claro ou escuro segue a preferência do próprio Anki (Ferramentas → Preferências → Aparência); cada tema define as duas variantes.

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
Ferramentas → **Temas…** (ou o botão *Config* da extensão em Ferramentas → Extensões) abre o seletor: lista de temas à
esquerda e, à direita, uma pré-visualização em **claro e escuro** lado a lado (o contorno marca o modo em uso agora).
Clique em *Aplicar* ou dê duplo clique no tema. "Padrão do Anki" desliga a extensão. A escolha fica no `config.json`
(`"theme": "flame"`). Janelas já abertas (navegador, editor) mostram o tema novo ao reabrir.

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
Crie `addon/themes/<id>.json`. O jeito simples é uma **paleta** de papéis por modo; a extensão calcula os 41 tokens:

```json
{ "id": "meu-tema", "name": "Meu tema", "description": "...",
  "palette": {
    "light": { "bg": "#fff", "fg": "#222", "accent": "#e33", "...": "..." },
    "dark":  { "bg": "#111", "fg": "#eee", "accent": "#f66", "...": "..." } } }
```
Papéis obrigatórios (hex `#rgb`/`#rrggbb`): `bg bg_elevated bg_inset bg_overlay bg_code fg fg_subtle fg_disabled fg_faint
border border_subtle border_strong button button_hi accent accent_dim link scrollbar scrollbar_hover scrollbar_active
shadow danger new learn review note`. Opcionais: `primary` e `primary_dim` (botão primário; padrão = `accent`/`accent_dim`),
`highlight`, `on_highlight`. Veja `catppuccin.json` e `gruvbox.json`.

Para ajustes finos acrescente `"tokens"` (vencem a paleta). Nomes = variáveis CSS do Anki sem `--` (lista em
`_aqt/colors.py`). Um valor pode ser uma cor, `$papel` ou `$papel@0.4` (o mesmo papel com 40% de opacidade). O Flame usa
só `tokens`, sem paleta; os dois formatos funcionam.

- Cores válidas: `#hex`, nomes, `rgb()/rgba()/hsl()/hsla()`. `extra_css`/`extra_qss` não podem conter `</`, `@import`,
  `url(` nem `javascript:`. Um arquivo inválido é ignorado (e registrado no stderr) sem afetar os outros.
- Pode definir só `light` ou só `dark`.
- Dica: o botão primário recebe texto branco; escolha `primary`/`primary_dim` escuros o bastante (contraste >= 3).

## Testes
```sh
python3 -I -m unittest discover -s tests -v
```
`test_engine.py` cobre validação, paleta, geração de CSS e aplicação/restauração das cores; `test_wiring.py` carrega a
extensão contra um `aqt` simulado; `test_picker.py` renderiza o seletor com PyQt6 real (pulado se não houver PyQt6; dentro
do Flatpak: `flatpak run --env=QT_QPA_PLATFORM=offscreen --command=python3 net.ankiweb.Anki -I -m unittest discover -s tests`,
com o projeto copiado para uma pasta que a sandbox enxergue). Para salvar um print do seletor: `PICKER_SHOT=arq.png`.
Os cinco temas foram validados contra a tabela de cores real do Anki 26.09.3 (todos os tokens existem) e checados quanto a
contraste WCAG (texto >= 4,5; botão primário >= 3).

## Limites conhecidos
- O reaplicar ao vivo usa atributos internos do Anki (`theme_manager._current_widget_style`); se falhar, reiniciar
  o Anki sempre aplica.
- Cartões com CSS próprio no tipo de nota que fixe cores (sem usar variáveis) não mudam.
