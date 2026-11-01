# 品牌与展示素材 / Brand and showcase media

圆环青色波形是正式 **Brand icon / Logo**；黑底白字版权头图是 **Hero image**，风格沿用软件 Splash，不是软件图标。图像均来自用户已选定资产或实际运行的内部候选，未改用其他图标、未添加设计稿界面。

The cyan circular waveform is the official brand icon / logo. The black-and-white copyright banner is a code-native hero in the splash style, not the app icon. Assets are user-selected or captured from the running candidate, not invented UI.

| 文件 / File | 角色 / Role | 来源 / Source |
| --- | --- | --- |
| [logo.png](logo.png) | 正式 Logo / Official logo | 用户选定透明1024px素材，像素未改 / Selected transparent asset, unchanged pixels |
| [hero.png](hero.png) | 首页头图 / README hero | SVG文字排版，左下灰色版权署名，无软件版本 / SVG wordmark and gray copyright signature, no software version |
| [social-preview.png](social-preview.png) | Social Preview 候选 | 同款版权头图，1280×640 / Same copyright hero |
| [music-workspace.png](music-workspace.png) | 音乐工作区 | 实际内部候选 / Running candidate |
| [analysis-report.png](analysis-report.png) | 分析结果 | 自有合成189秒素材；估计保持不确定 / Owned synthetic audio; uncertainty retained |
| [piano-roll.png](piano-roll.png) | 交互编辑器 | 实际音符及力度编辑 / Actual note and velocity editor |

每张图的来源字节摘要、发布摘要、候选版本、源码提交和转换记录见 [provenance.json](provenance.json)。源日志/文件的本机绝对路径不公开。工作区截图仅无损重压缩；Hero/Social改为可编辑SVG排版并渲染PNG，明确属于品牌图而非实际软件截图，不改功能截图或分析结果。未发现私人曲名、用户名、绝对路径、密钥、模型缓存或第三方桌面内容。

[Provenance](provenance.json) records source/published hashes, candidate version, commit and transformations without local absolute paths. Workspace screenshots are losslessly recompressed; hero/social are now rendered from editable SVG and explicitly classified as brand images rather than software screenshots. No private titles, usernames, paths, keys, caches or unrelated desktop content were found in the reviewed images.

## 版权与使用 / Copyright and use

Copyright © 2026 ryurikoneko。本目录的 PNG 图像作为本轮新增公开展示与品牌资产，版权保留；正式 Logo、Splash / Hero 与 Social Preview 不按根 MIT 自动授予品牌使用权。用户已授权本次项目主页展示。其他复用或品牌用途请先取得维护者明确许可；不宣称已注册商标或完成第三方独立权属认证。既有许可不追溯撤销。[完整资产条款](LICENSE.txt) · [品牌政策](../../TRADEMARKS.md)

Copyright © 2026 ryurikoneko. PNG images newly included here are reserved showcase/brand assets; the root MIT grant does not automatically license branding. The user authorized this repository presentation. Seek explicit maintainer permission for other reuse or branding. No trademark registration or independent ownership certification is claimed; prior grants are not revoked.

## Social Preview 计划 / Plan

已准备1280×640、低于1MB、实心黑底 PNG。符合 [GitHub 官方尺寸建议](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview)。本轮只准备候选，未上传到 Settings，未改变远端 Social Preview。

A solid-black 1280×640 PNG below 1MB is prepared per GitHub guidance. It has not been uploaded to repository Settings. The brand hero contains a copyright signature instead of a software version; the actual application splash keeps its dynamic version.

## 个人拟定主体与权属复核 / Individual-holder review

原署名ryurikoneko保留；用户拟定个人持有，不填写法定姓名。Logo、启动页和同源图像的实际作者/完整权属/历史授权未核清，PENDING_OWNER_REVIEW。既有声明不撤回早期可能已授出的许可；未来角色只占位、不公开私人源文件。[品牌清单](../brand/README.md)

The original public signature is retained. Individual ownership is a plan, not verified legal title. Authorship and prior grants remain pending review. Prior permissions are preserved; future character placeholders neither assert rights nor publish source art.

[可编辑头图源文件](hero-source.svg)仅包含黑底、白字DAWLoop和左下灰字Copyright (c) 2026 ryurikoneko。该署名是用户要求的公开品牌标记，不证明登记、法定身份或完整权属；相关PENDING_OWNER_REVIEW状态保持。软件内Splash实际版本显示不变。

新增 [音乐主页](music-home.png) 与 [模型管理](model-manager.png) 来自打包提交8123ae3的实际内部候选、隔离空userData；界面正确显示缺组件原因。这是开发机上的真实程序截图，不是干净Windows安装证明。
