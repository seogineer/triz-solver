# 39개 공학 파라미터 (매핑용 레퍼런스)

`data/parameters.json`에서 생성한 목록이다. 문제를 파라미터로 옮기는 **매핑 단계에서만** 읽는다. ID는 행렬 조회에 그대로 쓰이므로 이 표의 번호만 사용한다.

## 선택 요령

- 개선 파라미터: 사용자가 좋아지길 원하는 특성. 악화 파라미터: 그 결과 나빠지는 특성.
- 같은 특성이라도 대상이 **움직이는지** 고정됐는지에 따라 번호가 갈린다(1·2, 3·4, 5·6, 7·8, 15·16, 19·20).
- 헷갈리기 쉬운 쌍: 22(에너지 낭비) vs 19·20(에너지 소비량) vs 21(단위 시간당 출력), 30(외부에서 받는 유해 요인) vs 31(스스로 만드는 유해 요인), 27(고장 없이 동작) vs 15·16(작동 지속 시간).
- 후보는 개선·악화 각각 1~3개. 근거는 아래 정의와 키워드에서 찾는다. 딱 맞는 항목이 없으면 억지로 고르지 말고 사용자에게 다시 묻는다.

| ID | 한글명 | English | 정의 | 키워드 |
| --- | --- | --- | --- | --- |
| 1 | 움직이는 물체의 무게 | Weight of moving object | 이동하거나 움직일 수 있는 물체의 질량 또는 중량. 중력장에서 그 물체가 지지대에 가하는 힘도 포함한다. | 무게, 질량, 중량, 경량화, 이동체, weight, mass, lightweight, payload |
| 2 | 정지된 물체의 무게 | Weight of stationary object | 고정되어 움직이지 않는 물체(구조물·본체·프레임 등)의 질량 또는 중량. | 자중, 구조물 무게, 고정체, 본체 무게, static weight, structure weight, frame mass |
| 3 | 움직이는 물체의 길이 | Length of moving object | 움직이는 물체의 한 방향 치수. 길이·폭·높이·두께·지름 중 하나를 대표해서 쓴다. | 길이, 폭, 높이, 두께, 지름, 이동체 치수, length, width, height, thickness, diameter |
| 4 | 정지된 물체의 길이 | Length of stationary object | 고정된 물체의 한 방향 치수(길이·폭·높이·두께·지름). | 고정체 길이, 치수, 높이, 폭, 두께, dimension, static length, span |
| 5 | 움직이는 물체의 면적 | Area of moving object | 움직이는 물체의 표면, 단면, 투영 등이 차지하는 면적. | 면적, 표면적, 단면적, 접촉 면적, area, surface area, cross-section, footprint |
| 6 | 정지된 물체의 면적 | Area of stationary object | 고정된 물체의 표면이나 바닥, 단면이 차지하는 면적. | 설치 면적, 바닥 면적, 점유 면적, 표면적, floor area, footprint, static area |
| 7 | 움직이는 물체의 부피 | Volume of moving object | 움직이는 물체가 차지하는 공간의 부피. 용량이나 크기를 부피로 표현할 때 쓴다. | 부피, 체적, 용량, 크기, 소형화, volume, capacity, bulk, compactness |
| 8 | 정지된 물체의 부피 | Volume of stationary object | 고정된 물체가 차지하는 공간의 부피, 또는 그 내부 용적. | 설치 부피, 내부 용적, 용적, 체적, 공간 점유, enclosure volume, installed volume, static volume |
| 9 | 속도 | Speed | 물체가 움직이는 빠르기, 또는 공정·작업·반응이 진행되는 빠르기. | 속도, 빠르기, 속력, 응답 속도, 처리 속도, 가속, speed, velocity, rate, response speed |
| 10 | 힘 | Force | 물체 사이의 상호작용을 바꾸려는 밀거나 당기는 작용. 하중, 토크, 추력 등을 포함한다. | 힘, 하중, 토크, 추력, 압축력, 견인, force, load, torque, thrust, pull |
| 11 | 응력 또는 압력 | Stress or pressure | 단위 면적에 걸리는 힘 또는 재료 내부에 생기는 응력. 압력, 인장·압축 응력, 유체 압력을 포함한다. | 압력, 응력, 스트레스, 내압, 진공, pressure, stress, tension, compression |
| 12 | 형상 | Shape | 물체의 외형과 윤곽, 겉모양. 형태를 바꾸거나 유지하는 능력도 포함한다. | 형상, 모양, 형태, 외형, 윤곽, 곡면, shape, form, contour, geometry |
| 13 | 구성의 안정성 | Stability of composition | 물체의 구성과 조성이 시간과 조건 변화에도 유지되는 정도. 분해, 변형, 열화, 마모에 대한 저항을 포함한다. | 안정성, 구성 안정, 열화, 변질, 변형, 부식, 안정, stability, integrity, degradation, corrosion, deformation |
| 14 | 강도 | Strength | 외력이 가해져도 파손되지 않고 버티는 능력. 인장·굽힘·충격에 대한 견고함. | 강도, 견고, 파손, 파단, 충격 저항, 내하중, strength, robustness, breakage, toughness, fracture |
| 15 | 작동 지속 시간 (움직임) | Duration of action (moving) | 움직이는 물체가 기능을 유지하며 작동할 수 있는 시간. 수명과 연속 작동 시간을 포함한다. | 작동 시간, 수명, 내구성, 지속 시간, 연속 작동, durability, service life, runtime, endurance, lifetime |
| 16 | 작동 지속 시간 (정지) | Duration of action (stationary) | 고정된 물체가 기능을 유지하며 작동할 수 있는 시간. 수명, 보존 기간, 내구 연한을 포함한다. | 정지체 수명, 보존 기간, 내구 연한, 지속성, 유효 기간, shelf life, static durability, service life, longevity |
| 17 | 온도 | Temperature | 물체나 시스템의 열적 상태. 온도 자체와 가열·냉각·열 관리 문제를 포함한다. | 온도, 열, 가열, 냉각, 방열, 발열, temperature, heat, cooling, thermal, overheating |
| 18 | 조명 강도 | Illumination intensity | 단위 면적에 도달하는 빛의 양이나 밝기. 조명, 시인성, 광학적 특성도 포함한다. | 조도, 밝기, 조명, 광량, 시인성, 빛, illumination, brightness, lighting, luminance, visibility |
| 19 | 에너지 사용 (움직이는 물체) | Use of energy (moving object) | 움직이는 물체가 작업을 하는 데 쓰는 에너지. 전력이나 연료 소비량으로 나타난다. | 에너지 소비, 전력 소비, 연료 소비, 배터리, 이동체 전력, energy consumption, power draw, fuel use, battery |
| 20 | 에너지 사용 (정지) | Use of energy (stationary) | 고정된 물체가 작업을 하는 데 쓰는 에너지. 상시 가동 설비의 전력·연료 소비 등. | 설비 에너지, 고정 설비 전력, 대기 전력, 전기료, stationary energy use, standby power, energy bill, plant energy |
| 21 | 동력 | Power | 단위 시간당 사용하거나 전달하는 에너지의 비율. 출력과 작업률을 뜻한다. | 동력, 출력, 전력, 마력, 파워, 와트, power, output, wattage, horsepower |
| 22 | 에너지 손실 | Loss of energy | 유용한 작업에 기여하지 못하고 낭비되는 에너지. 열 손실, 마찰, 누설, 효율 저하 등. | 에너지 손실, 효율, 열손실, 마찰 손실, 낭비, energy loss, efficiency, waste heat, friction loss |
| 23 | 물질 손실 | Loss of substance | 시스템에서 물질, 재료, 부품, 구성요소가 일부나 전부 사라지는 것. 마모, 누출, 증발, 소모. | 물질 손실, 마모, 누출, 증발, 소모, 소실, material loss, wear, leakage, evaporation, consumption |
| 24 | 정보 손실 | Loss of information | 데이터나 정보의 일부 또는 전부가 사라지거나 접근할 수 없게 되는 것. 신호 손실과 노이즈를 포함한다. | 정보 손실, 데이터 손실, 신호 손실, 잡음, 노이즈, 유실, data loss, information loss, signal loss, noise |
| 25 | 시간 손실 | Loss of time | 어떤 활동을 하는 데 걸리는 시간. 대기, 지연, 사이클 타임, 리드타임을 포함한다. | 시간 손실, 지연, 대기 시간, 사이클 타임, 리드타임, 소요 시간, delay, waiting time, cycle time, lead time, latency |
| 26 | 물질/물체의 양 | Quantity of substance/matter | 시스템을 이루는 재료, 물질, 부품의 수나 양. 늘거나 줄일 수 있는 자원의 양. | 물질량, 재료량, 부품 수, 사용량, 자재, quantity, amount of material, part count, material use |
| 27 | 신뢰성 | Reliability | 정해진 조건과 기간 동안 요구된 기능을 정상적으로 수행하는 능력. 고장률이 낮을수록 높다. | 신뢰성, 고장, 고장률, 안정 동작, 가용성, 오작동, reliability, failure rate, fault, uptime, dependability |
| 28 | 측정 정확도 | Measurement accuracy | 측정값이 실제값에 가까운 정도. 오차, 분해능, 재현성을 포함한다. | 측정 정확도, 정확도, 오차, 분해능, 재현성, 정밀 측정, accuracy, measurement error, resolution, repeatability |
| 29 | 제조 정밀도 | Manufacturing precision | 제작된 결과가 요구한 사양과 공차에 일치하는 정도. 가공·조립의 정밀함. | 제조 정밀도, 가공 정밀도, 공차, 치수 정밀, 조립 정밀, manufacturing precision, tolerance, machining accuracy, fit |
| 30 | 물체가 받는 유해 요인 | Object-affected harmful factors | 외부에서 물체에 작용해 그 성능이나 품질을 떨어뜨리는 유해 요인. 오염, 외부 진동, 열, 습기, 이물질 등. | 외부 유해 요인, 오염, 외부 진동, 습기, 이물질, 환경 영향, external harm, contamination, moisture, interference, environmental damage |
| 31 | 물체가 발생시키는 유해 요인 | Object-generated harmful factors | 물체가 작동하면서 스스로 만들어 주변이나 사용자, 시스템에 피해를 주는 유해 요인. 소음, 진동, 배기, 발열, 폐기물 등. | 유해한 부작용, 소음, 배출, 배기가스, 부작용, 폐기물, 진동 발생, side effect, noise, emission, waste, harmful output |
| 32 | 제조 용이성 | Ease of manufacture | 제품을 만들고 조립하기 쉽고 단순한 정도. 공정 수와 제작 난이도가 낮을수록 높다. | 제조 용이성, 제작 용이, 조립성, 생산 편의, 양산성, manufacturability, ease of assembly, easy to build, producibility |
| 33 | 작동 용이성 | Ease of operation | 사용자가 적은 단계와 노력으로 시스템을 다루고 조작할 수 있는 정도. 사용 편의성. | 작동 용이성, 사용 편의, 조작성, 사용성, 간편, usability, ease of use, operability, user-friendly |
| 34 | 수리 용이성 | Ease of repair | 고장이나 손상을 찾고 고치고 정비하는 것이 쉬운 정도. 유지보수의 시간과 비용이 낮을수록 높다. | 수리 용이성, 정비, 유지보수, 서비스성, 교체 용이, serviceability, maintainability, repairability, ease of repair |
| 35 | 적응성 또는 다용도성 | Adaptability or versatility | 바뀌는 외부 조건이나 다양한 용도, 요구에 맞춰 시스템이 스스로 적응하거나 쓰일 수 있는 정도. 범용성과 유연성. | 적응성, 다용도, 범용성, 유연성, 호환성, 확장성, adaptability, versatility, flexibility, compatibility, scalability |
| 36 | 장치 복잡성 | Device complexity | 시스템을 이루는 요소의 수와 그 사이 관계가 얽힌 정도. 구조나 사용 방법이 복잡할수록 높다. | 장치 복잡성, 복잡도, 부품 수, 구조 복잡, 상호 의존, complexity, number of components, intricacy, interdependence |
| 37 | 감지/측정의 어려움 | Difficulty of detecting/measuring | 시스템의 상태를 감지하거나 측정하기 어렵고 비용이 많이 드는 정도. 측정기 자체가 복잡하거나 비싼 경우를 포함한다. | 감지 어려움, 측정 난이도, 모니터링, 검사 난이도, 비파괴 검사, detectability, difficulty of measuring, monitoring, inspection, sensing |
| 38 | 자동화 정도 | Extent of automation | 사람이 개입하지 않고도 시스템이 스스로 동작하는 정도. 수동, 반자동, 완전 자동 순으로 높아진다. | 자동화, 자율, 무인, 자동 제어, 수동 작업 감소, automation, autonomy, unattended, automatic control, hands-free |
| 39 | 생산성 | Productivity | 단위 시간당 산출량이나 작업 처리량. 같은 시간에 더 많은 결과를 내는 정도. | 생산성, 처리량, 산출량, 효율, 수율, throughput, productivity, output rate, yield |
