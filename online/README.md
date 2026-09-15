# Cat Desktop Pet

写实照片风猫桌宠：用自家猫的两张照片（睁眼 + 闭眼）做一只会呼吸、眨眼、摆动的桌面宠物。

## 依赖
- Python 3
- 依赖见 `requirements.txt`

## 使用
1. 准备素材：把睁眼照、闭眼照分别放到 `assets/src/cat_open.jpg`、`assets/src/cat_closed.jpg`
2. 生成透明 PNG：`python -m pet.prepare_assets`（首次需联网下载 rembg 模型）
3. 运行：`python -m pet.main`

## 交互
- 拖动：移动位置
- 左键点击：随机反应（眨眼/惊吓/晃头）
- 右键：置顶开关 / 退出

## 打包
`python -m PyInstaller build.spec`，产物在 `dist/cat-pet.exe`
