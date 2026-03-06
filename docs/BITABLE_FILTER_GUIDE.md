# 记录筛选参数填写说明

在多维表格部分接口中，可以通过请求参数 `filter` 设置筛选条件，筛选出需要的记录。

## 1. 参数结构

| 参数名称 | 数据类型 | 描述 |
|---|---|---|
| `filter` | `object` | 包含条件筛选信息的对象 |
| `filter.conjunction` | `string` | 条件之间的逻辑连接词，可选：`and`、`or` |
| `filter.conditions` | `array` | 筛选条件集合 |
| `filter.conditions[].field_name` | `string` | 条件字段名 |
| `filter.conditions[].operator` | `string` | 条件运算符 |
| `filter.conditions[].value` | `string[]` | 条件值，可填单值或多值数组 |

## 2. `operator` 可选值

- `is`：等于
- `isNot`：不等于（不支持日期字段）
- `contains`：包含（不支持日期字段）
- `doesNotContain`：不包含（不支持日期字段）
- `isEmpty`：为空
- `isNotEmpty`：不为空
- `isGreater`：大于
- `isGreaterEqual`：大于等于（不支持日期字段）
- `isLess`：小于
- `isLessEqual`：小于等于（不支持日期字段）
- `like`：LIKE（暂未支持）
- `in`：IN（暂未支持）

## 3. 通用结构示例

```json
{
  "filter": {
    "conjunction": "and",
    "conditions": [
      {
        "field_name": "字段1",
        "operator": "is",
        "value": [
          "文本内容"
        ]
      }
    ]
  }
}
```

## 4. 业务示例

员工销售额表示例数据：

| 员工名称 | 职位 | 销售额 |
|---|---|---|
| 张小一 | 初级销售员 | 10000.0 |
| 张小二 | 初级销售员 | 15000.0 |
| 张小三 | 初级销售员 | 20000.0 |
| 张小四 | 高级销售员 | 30000.0 |
| 张小五 | 高级销售员 | 50000.0 |
| 张小六 | 销售经理 | 100000.0 |

### 示例 A：职位=初级销售员 且 销售额>10000

```json
{
  "filter": {
    "conjunction": "and",
    "conditions": [
      {
        "field_name": "职位",
        "operator": "is",
        "value": [
          "初级销售员"
        ]
      },
      {
        "field_name": "销售额",
        "operator": "isGreater",
        "value": [
          "10000.0"
        ]
      }
    ]
  }
}
```

### 示例 B：职位=高级销售员 或 销售额>20000

```json
{
  "filter": {
    "conjunction": "or",
    "conditions": [
      {
        "field_name": "职位",
        "operator": "is",
        "value": [
          "高级销售员"
        ]
      },
      {
        "field_name": "销售额",
        "operator": "isGreater",
        "value": [
          "20000.0"
        ]
      }
    ]
  }
}
```
