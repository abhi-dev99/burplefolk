import html
from typing import Dict, List, Optional, Set, Tuple


def mermaid_type_from_dtype(dtype: str) -> str:
    value = dtype.lower()
    if "int" in value:
        return "INT"
    if "float" in value or "double" in value or "decimal" in value:
        return "DECIMAL"
    if "date" in value or "time" in value:
        return "DATETIME"
    if "bool" in value:
        return "BOOLEAN"
    return "STRING"


def infer_display_type(column_name: str, sample_dtype: str) -> str:
    col = column_name.lower()
    if col == "id" or col.endswith("_id"):
        return "INT"
    return mermaid_type_from_dtype(sample_dtype)


DOMAIN_ORDER = {"sales": 0, "core": 1, "production": 2, "other": 3}


def _infer_domain(table_name: str, domain_hints: Optional[Dict[str, str]] = None) -> str:
    table = table_name.lower()
    if domain_hints:
        hinted = domain_hints.get(table_name) or domain_hints.get(table)
        if hinted in DOMAIN_ORDER:
            return hinted

    sales_tokens = {"order", "customer", "store", "staff", "payment", "invoice", "shipment"}
    production_tokens = {"product", "category", "brand", "stock", "inventory", "supplier", "warehouse"}

    if any(token in table for token in production_tokens):
        return "production"
    if any(token in table for token in sales_tokens):
        return "sales"
    return "core"


def _ordered_columns(profile: Dict, pk_set: Set[str], fk_lookup: Set[Tuple[str, str]]) -> List[Dict]:
    pk_cols: List[Dict] = []
    fk_cols: List[Dict] = []
    other_cols: List[Dict] = []

    for cp in profile["column_profiles"]:
        col = cp["column"]
        if col in pk_set:
            pk_cols.append(cp)
        elif (profile["table"], col) in fk_lookup:
            fk_cols.append(cp)
        else:
            other_cols.append(cp)

    return pk_cols + fk_cols + other_cols


def _is_descriptor_column(column_name: str) -> bool:
    value = column_name.lower()
    return any(token in value for token in ["name", "title", "type", "status", "date"])


def _select_columns_for_view(
    profile: Dict,
    pk_set: Set[str],
    fk_lookup: Set[Tuple[str, str]],
    view_mode: str,
) -> List[Dict]:
    ordered = _ordered_columns(profile, pk_set, fk_lookup)
    if view_mode == "full":
        return ordered

    compact: List[Dict] = []
    for cp in ordered:
        col = cp["column"]
        if col in pk_set or (profile["table"], col) in fk_lookup:
            compact.append(cp)

    for cp in ordered:
        if len(compact) >= 10:
            break
        if cp in compact:
            continue
        if _is_descriptor_column(cp["column"]):
            compact.append(cp)

    return compact or ordered


def format_mermaid(
    table_profiles: List[Dict],
    relationships: List[Dict],
    pk_map: Dict[str, List[str]],
    view_mode: str = "full",
) -> str:
    lines = ["erDiagram"]

    selected_mode = "keys" if view_mode == "keys" else "full"
    fk_lookup = {(rel["child_table"], rel["child_column"]) for rel in relationships}

    for profile in sorted(table_profiles, key=lambda p: p["table"]):
        table = profile["table"].upper()
        pk_set = set(pk_map.get(profile["table"], []))

        lines.append(f"  {table} {{")
        for cp in _select_columns_for_view(profile, pk_set, fk_lookup, selected_mode):
            col = cp["column"]
            dtype = infer_display_type(col, cp["sample_dtype"])
            is_pk = col in pk_set
            is_fk = (profile["table"], col) in fk_lookup

            if is_pk:
                suffix = " PK"
            elif is_fk:
                suffix = " FK"
            else:
                suffix = ""

            lines.append(f"    {dtype} {col}{suffix}")
        lines.append("  }")

    seen = set()
    for rel in sorted(
        relationships,
        key=lambda r: (r["parent_table"], r["child_table"], r["child_column"], r["parent_column"]),
    ):
        key = (rel["parent_table"], rel["child_table"], rel["child_column"])
        if key in seen:
            continue
        seen.add(key)

        connector = "||--o{" if rel.get("relation_type") == "many-to-one" else "||--||"
        child_column = rel["child_column"]
        parent_column = rel["parent_column"]
        edge_label = child_column if child_column == parent_column else f"{child_column}_to_{parent_column}"
        lines.append(f"  {rel['parent_table'].upper()} {connector} {rel['child_table'].upper()} : {edge_label}")

    return "\n".join(lines)


def _compute_layers(table_names: List[str], relationships: List[Dict]) -> Dict[str, int]:
    children: Dict[str, set] = {name: set() for name in table_names}
    indegree: Dict[str, int] = {name: 0 for name in table_names}

    for rel in relationships:
        parent = rel["parent_table"]
        child = rel["child_table"]
        if parent == child:
            continue
        if parent not in children or child not in children:
            continue
        if child in children[parent]:
            continue
        children[parent].add(child)
        indegree[child] += 1

    layers: Dict[str, int] = {name: 0 for name in table_names}
    queue = [name for name in table_names if indegree[name] == 0]

    while queue:
        node = queue.pop(0)
        for child in sorted(children[node]):
            layers[child] = max(layers[child], layers[node] + 1)
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    return layers


def _build_order_rank(table_names: List[str], table_order_override: Optional[List[str]]) -> Dict[str, int]:
    rank = {name: idx for idx, name in enumerate(sorted(table_names))}
    if not table_order_override:
        return rank

    cursor = 0
    seen = set()
    for table in table_order_override:
        if table not in rank or table in seen:
            continue
        rank[table] = cursor
        seen.add(table)
        cursor += 1

    for table in sorted(table_names):
        if table in seen:
            continue
        rank[table] = cursor
        cursor += 1

    return rank


def _orthogonal_path(points: List[Tuple[float, float]]) -> str:
    if not points:
        return ""
    path = [f"M {points[0][0]:.1f} {points[0][1]:.1f}"]
    for x, y in points[1:]:
        path.append(f"L {x:.1f} {y:.1f}")
    return " ".join(path)


def _column_anchor(entity: Dict, column_name: str, side: str) -> Tuple[float, float]:
    header_h = entity.get("header_h", 34)
    row_h = entity.get("row_h", 20)
    col_index = entity.get("column_index", {}).get(column_name)

    if col_index is None:
        y = entity["y"] + (entity["h"] / 2.0)
    else:
        y = entity["y"] + header_h + (col_index * row_h) + (row_h / 2.0)

    if side == "R":
        x = entity["x"] + entity["w"]
    elif side == "L":
        x = entity["x"]
    elif side == "T":
        x = entity["x"] + (entity["w"] / 2.0)
        y = entity["y"]
    else:  # B
        x = entity["x"] + (entity["w"] / 2.0)
        y = entity["y"] + entity["h"]

    return x, y


def _text_px_width(text: str, bold: bool = False) -> float:
    if not text:
        return 0.0
    per_char = 6.9 if bold else 6.3
    return max(12.0, len(str(text)) * per_char)


def _vertical_lane_hits_entity(
    lane_x: float,
    y1: float,
    y2: float,
    entities: Dict[str, Dict],
    excluded: Set[str],
) -> bool:
    seg_top = min(y1, y2)
    seg_bottom = max(y1, y2)
    for table_name, entity in entities.items():
        if table_name in excluded:
            continue
        ex1 = entity["x"] - 6.0
        ex2 = entity["x"] + entity["w"] + 6.0
        ey1 = entity["y"] - 6.0
        ey2 = entity["y"] + entity["h"] + 6.0
        if ex1 <= lane_x <= ex2 and not (seg_bottom < ey1 or seg_top > ey2):
            return True
    return False


def _horizontal_lane_hits_entity(
    lane_y: float,
    x1: float,
    x2: float,
    entities: Dict[str, Dict],
    excluded: Set[str],
) -> bool:
    seg_left = min(x1, x2)
    seg_right = max(x1, x2)
    for table_name, entity in entities.items():
        if table_name in excluded:
            continue
        ex1 = entity["x"] - 6.0
        ex2 = entity["x"] + entity["w"] + 6.0
        ey1 = entity["y"] - 6.0
        ey2 = entity["y"] + entity["h"] + 6.0
        if ey1 <= lane_y <= ey2 and not (seg_right < ex1 or seg_left > ex2):
            return True
    return False


def _choose_clear_vertical_lane(
    base_x: float,
    y1: float,
    y2: float,
    entities: Dict[str, Dict],
    excluded: Set[str],
    step: float = 20.0,
    tries: int = 14,
) -> float:
    candidates = [0]
    for i in range(1, tries + 1):
        candidates.append(i)
        candidates.append(-i)

    for offset in candidates:
        lane_x = base_x + (offset * step)
        if not _vertical_lane_hits_entity(lane_x, y1, y2, entities, excluded):
            return lane_x
    return base_x


def _choose_clear_horizontal_lane(
    base_y: float,
    x1: float,
    x2: float,
    entities: Dict[str, Dict],
    excluded: Set[str],
    step: float = 20.0,
    tries: int = 14,
) -> float:
    candidates = [0]
    for i in range(1, tries + 1):
        candidates.append(i)
        candidates.append(-i)

    for offset in candidates:
        lane_y = base_y + (offset * step)
        if not _horizontal_lane_hits_entity(lane_y, x1, x2, entities, excluded):
            return lane_y
    return base_y


def _build_scene(
    table_profiles: List[Dict],
    relationships: List[Dict],
    pk_map: Dict[str, List[str]],
    view_mode: str,
    layout_direction: str,
    table_order_override: Optional[List[str]] = None,
    domain_hints: Optional[Dict[str, str]] = None,
) -> Tuple[Dict[str, Dict], List[Dict], List[Dict], int, int]:
    fk_lookup = {(rel["child_table"], rel["child_column"]) for rel in relationships}

    entities: Dict[str, Dict] = {}
    for profile in sorted(table_profiles, key=lambda p: p["table"]):
        table = profile["table"]
        pk_set = set(pk_map.get(table, []))
        columns = []
        for cp in _select_columns_for_view(profile, pk_set, fk_lookup, view_mode):
            col = cp["column"]
            role = "PK" if col in pk_set else ("FK" if (table, col) in fk_lookup else "")
            columns.append(
                {
                    "name": col,
                    "dtype": infer_display_type(col, cp["sample_dtype"]),
                    "role": role,
                }
            )

        if not columns:
            columns = [{"name": "(no columns)", "dtype": "STRING", "role": ""}]

        header_h = 34
        row_h = 22
        dtype_col_w = max((_text_px_width(col["dtype"], bold=True) for col in columns), default=24.0) + 8.0
        name_col_w = max((_text_px_width(col["name"]) for col in columns), default=48.0) + 6.0
        role_col_w = max((_text_px_width(col["role"], bold=True) for col in columns if col.get("role")), default=0.0)

        left_pad = 12.0
        right_pad = 12.0
        dtype_x = left_pad
        name_x = dtype_x + dtype_col_w + 16.0
        role_gap = 14.0 if role_col_w > 0 else 0.0

        raw_w = left_pad + dtype_col_w + 16.0 + name_col_w + role_gap + role_col_w + right_pad
        title_w = _text_px_width(table.upper(), bold=True) + 36.0
        card_w = min(460.0, max(220.0, raw_w, title_w))
        role_x = card_w - right_pad
        card_h = header_h + (len(columns) * row_h) + 14

        entities[table] = {
            "table": table,
            "title": table.upper(),
            "columns": columns,
            "w": card_w,
            "h": card_h,
            "x": 0.0,
            "y": 0.0,
            "header_h": header_h,
            "row_h": row_h,
            "domain": _infer_domain(table, domain_hints),
            "column_index": {col["name"]: idx for idx, col in enumerate(columns)},
            "dtype_x": dtype_x,
            "name_x": name_x,
            "role_x": role_x,
        }

    if not entities:
        placeholder = {
            "placeholder": {
                "table": "placeholder",
                "title": "NO TABLES",
                "columns": [],
                "w": 300,
                "h": 80,
                "x": 24.0,
                "y": 24.0,
                "header_h": 34,
                "row_h": 20,
                "domain": "other",
                "column_index": {},
            }
        }
        return placeholder, [], [], 800, 500

    layers = _compute_layers(list(entities.keys()), relationships)
    order_rank = _build_order_rank(list(entities.keys()), table_order_override)
    layer_groups: Dict[int, List[str]] = {}
    for table in sorted(
        entities.keys(),
        key=lambda t: (layers.get(t, 0), DOMAIN_ORDER.get(entities[t]["domain"], 99), order_rank.get(t, 999), t),
    ):
        layer_groups.setdefault(layers.get(table, 0), []).append(table)

    pad = 40
    lane_gap = 182
    stack_gap = 34
    domain_gap = 36
    max_w = max((entity["w"] for entity in entities.values()), default=320)
    max_h = max((entity["h"] for entity in entities.values()), default=120)
    domain_sequence = ["sales", "core", "production", "other"]

    if layout_direction == "TB":
        domain_required_width: Dict[str, float] = {domain: 0.0 for domain in domain_sequence}
        for layer in layer_groups.values():
            grouped = {domain: [] for domain in domain_sequence}
            for table in layer:
                grouped.setdefault(entities[table]["domain"], []).append(table)
            for domain in domain_sequence:
                members = grouped.get(domain, [])
                if not members:
                    continue
                required = float(sum(entities[t]["w"] for t in members) + (max(0, len(members) - 1) * stack_gap))
                domain_required_width[domain] = max(domain_required_width[domain], required)

        domain_base_x: Dict[str, float] = {}
        x_cursor = float(pad)
        for domain in domain_sequence:
            domain_base_x[domain] = x_cursor
            span = max(0.0, domain_required_width.get(domain, 0.0))
            x_cursor += span + float(domain_gap)

        for layer in sorted(layer_groups.keys()):
            y_base = float(pad + layer * (max_h + lane_gap))
            grouped = {domain: [] for domain in domain_sequence}
            for table in layer_groups[layer]:
                grouped.setdefault(entities[table]["domain"], []).append(table)

            domain_offsets = {domain: domain_base_x[domain] for domain in domain_sequence}
            for domain in domain_sequence:
                members = grouped.get(domain, [])
                for table in members:
                    entity = entities[table]
                    entity["x"] = domain_offsets[domain]
                    entity["y"] = y_base
                    domain_offsets[domain] += float(entity["w"] + stack_gap)
    else:
        domain_required_height: Dict[str, float] = {domain: 0.0 for domain in domain_sequence}
        for layer in layer_groups.values():
            grouped = {domain: [] for domain in domain_sequence}
            for table in layer:
                grouped.setdefault(entities[table]["domain"], []).append(table)
            for domain in domain_sequence:
                members = grouped.get(domain, [])
                if not members:
                    continue
                required = float(sum(entities[t]["h"] for t in members) + (max(0, len(members) - 1) * stack_gap))
                domain_required_height[domain] = max(domain_required_height[domain], required)

        domain_base_y: Dict[str, float] = {}
        y_cursor = float(pad)
        for domain in domain_sequence:
            domain_base_y[domain] = y_cursor
            span = max(0.0, domain_required_height.get(domain, 0.0))
            y_cursor += span + float(domain_gap)

        for layer in sorted(layer_groups.keys()):
            x_base = float(pad + layer * (max_w + lane_gap))
            grouped = {domain: [] for domain in domain_sequence}
            for table in layer_groups[layer]:
                grouped.setdefault(entities[table]["domain"], []).append(table)

            domain_offsets = {domain: domain_base_y[domain] for domain in domain_sequence}
            for domain in domain_sequence:
                members = grouped.get(domain, [])
                for table in members:
                    entity = entities[table]
                    entity["x"] = x_base
                    entity["y"] = domain_offsets[domain]
                    domain_offsets[domain] += float(entity["h"] + stack_gap)

    domain_regions: List[Dict] = []
    for domain in ["sales", "core", "production"]:
        members = [entity for entity in entities.values() if entity["domain"] == domain]
        if len(members) < 2:
            continue
        min_x = min(entity["x"] for entity in members) - 14
        min_y = min(entity["y"] for entity in members) - 18
        max_x = max(entity["x"] + entity["w"] for entity in members) + 14
        max_y = max(entity["y"] + entity["h"] for entity in members) + 16
        domain_regions.append(
            {
                "domain": domain,
                "label": domain.upper(),
                "x": min_x,
                "y": min_y,
                "w": max_x - min_x,
                "h": max_y - min_y,
            }
        )

    raw_edges: List[Dict] = []
    seen_edges = set()
    for rel in sorted(
        relationships,
        key=lambda r: (r["parent_table"], r["child_table"], r["child_column"], r["parent_column"]),
    ):
        parent = rel["parent_table"]
        child = rel["child_table"]
        if parent not in entities or child not in entities:
            continue

        edge_key = (parent, child, rel["child_column"], rel["parent_column"])
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)

        parent_entity = entities[parent]
        child_entity = entities[child]
        label = rel["child_column"] if rel["child_column"] == rel["parent_column"] else f"{rel['child_column']} -> {rel['parent_column']}"

        if parent == child:
            orientation = "SELF"
            start_side = "R"
            end_side = "R"
        elif layout_direction == "TB":
            orientation = "V"
            parent_center_y = parent_entity["y"] + (parent_entity["h"] / 2.0)
            child_center_y = child_entity["y"] + (child_entity["h"] / 2.0)
            downwards = child_center_y >= parent_center_y
            start_side = "B" if downwards else "T"
            end_side = "T" if downwards else "B"
        else:
            orientation = "H"
            parent_center_x = parent_entity["x"] + (parent_entity["w"] / 2.0)
            child_center_x = child_entity["x"] + (child_entity["w"] / 2.0)
            rightwards = child_center_x >= parent_center_x
            start_side = "R" if rightwards else "L"
            end_side = "L" if rightwards else "R"

        raw_edges.append(
            {
                "parent": parent,
                "child": child,
                "parent_column": rel["parent_column"],
                "child_column": rel["child_column"],
                "label": label,
                "orientation": orientation,
                "start_side": start_side,
                "end_side": end_side,
            }
        )

    out_groups: Dict[Tuple[str, str], List[int]] = {}
    in_groups: Dict[Tuple[str, str], List[int]] = {}
    pair_groups: Dict[Tuple[str, str, str], List[int]] = {}
    for idx, edge in enumerate(raw_edges):
        if edge["orientation"] == "SELF":
            continue
        out_groups.setdefault((edge["parent"], edge["start_side"]), []).append(idx)
        in_groups.setdefault((edge["child"], edge["end_side"]), []).append(idx)
        pair_key = (
            min(edge["parent"], edge["child"]),
            max(edge["parent"], edge["child"]),
            edge["orientation"],
        )
        pair_groups.setdefault(pair_key, []).append(idx)

    def _assign_slots(groups: Dict[Tuple[str, str], List[int]], target_type: str) -> Dict[int, Tuple[int, int]]:
        slots: Dict[int, Tuple[int, int]] = {}
        for indices in groups.values():
            if len(indices) == 1:
                slots[indices[0]] = (0, 1)
                continue

            if target_type == "out":
                indices.sort(
                    key=lambda i: (
                        entities[raw_edges[i]["child"]]["y"],
                        entities[raw_edges[i]["child"]]["x"],
                        raw_edges[i]["child_column"],
                    )
                )
            else:
                indices.sort(
                    key=lambda i: (
                        entities[raw_edges[i]["parent"]]["y"],
                        entities[raw_edges[i]["parent"]]["x"],
                        raw_edges[i]["parent_column"],
                    )
                )

            size = len(indices)
            for slot, edge_index in enumerate(indices):
                slots[edge_index] = (slot, size)
        return slots

    out_slots = _assign_slots(out_groups, "out")
    in_slots = _assign_slots(in_groups, "in")

    pair_slots: Dict[int, Tuple[int, int]] = {}
    for indices in pair_groups.values():
        indices.sort(key=lambda i: (raw_edges[i]["parent_column"], raw_edges[i]["child_column"], raw_edges[i]["label"]))
        size = len(indices)
        for slot, edge_index in enumerate(indices):
            pair_slots[edge_index] = (slot, size)

    edges: List[Dict] = []
    for idx, edge in enumerate(raw_edges):
        parent_entity = entities[edge["parent"]]
        child_entity = entities[edge["child"]]

        if edge["orientation"] == "SELF":
            base_x, base_y = _column_anchor(parent_entity, edge["parent_column"], "R")
            slot, size = out_slots.get(idx, (0, 1))
            centered = slot - ((size - 1) / 2.0)
            loop_width = 44.0 + (abs(centered) * 12.0)
            loop_height = 36.0 + (abs(centered) * 8.0)

            points = [
                (base_x, base_y),
                (base_x + 12.0, base_y),
                (base_x + loop_width, base_y),
                (base_x + loop_width, base_y + loop_height),
                (base_x + 12.0, base_y + loop_height),
                (base_x, base_y + loop_height),
            ]
            path = _orthogonal_path(points)
            label_x = base_x + loop_width + 4.0
            label_y = base_y + (loop_height / 2.0) - 4.0
            edges.append({"path": path, "label": edge["label"], "label_x": label_x, "label_y": label_y})
            continue

        start_x, start_y = _column_anchor(parent_entity, edge["parent_column"], edge["start_side"])
        end_x, end_y = _column_anchor(child_entity, edge["child_column"], edge["end_side"])

        out_slot, out_size = out_slots.get(idx, (0, 1))
        in_slot, in_size = in_slots.get(idx, (0, 1))
        pair_slot, pair_size = pair_slots.get(idx, (0, 1))

        out_centered = out_slot - ((out_size - 1) / 2.0)
        in_centered = in_slot - ((in_size - 1) / 2.0)
        pair_centered = pair_slot - ((pair_size - 1) / 2.0)

        if edge["orientation"] == "H":
            start_y += out_centered * 8.0
            end_y += in_centered * 8.0
            forward = 1.0 if edge["start_side"] == "R" else -1.0
            stub = 22.0

            p1_x = start_x + (forward * stub)
            p4_x = end_x - (forward * stub)
            lane_x = ((p1_x + p4_x) / 2.0) + (pair_centered * 18.0)

            if forward > 0:
                lane_x = max(min(lane_x, p4_x - 12.0), p1_x + 12.0)
            else:
                lane_x = min(max(lane_x, p4_x + 12.0), p1_x - 12.0)

            lane_x = _choose_clear_vertical_lane(
                lane_x,
                start_y,
                end_y,
                entities,
                excluded={edge["parent"], edge["child"]},
                step=20.0,
                tries=18,
            )

            points = [
                (start_x, start_y),
                (p1_x, start_y),
                (lane_x, start_y),
                (lane_x, end_y),
                (p4_x, end_y),
                (end_x, end_y),
            ]
            label_x = lane_x + (6.0 if forward > 0 else -6.0)
            label_y = ((start_y + end_y) / 2.0) - 5.0
        else:
            start_x += out_centered * 8.0
            end_x += in_centered * 8.0
            downward = 1.0 if edge["start_side"] == "B" else -1.0
            stub = 22.0

            p1_y = start_y + (downward * stub)
            p4_y = end_y - (downward * stub)
            lane_y = ((p1_y + p4_y) / 2.0) + (pair_centered * 18.0)

            if downward > 0:
                lane_y = max(min(lane_y, p4_y - 12.0), p1_y + 12.0)
            else:
                lane_y = min(max(lane_y, p4_y + 12.0), p1_y - 12.0)

            lane_y = _choose_clear_horizontal_lane(
                lane_y,
                start_x,
                end_x,
                entities,
                excluded={edge["parent"], edge["child"]},
                step=20.0,
                tries=18,
            )

            points = [
                (start_x, start_y),
                (start_x, p1_y),
                (start_x, lane_y),
                (end_x, lane_y),
                (end_x, p4_y),
                (end_x, end_y),
            ]
            label_x = ((start_x + end_x) / 2.0) + 6.0
            label_y = lane_y - 6.0

        edges.append(
            {
                "path": _orthogonal_path(points),
                "label": edge["label"],
                "label_x": label_x,
                "label_y": label_y,
            }
        )

    max_x = max((entity["x"] + entity["w"] for entity in entities.values()), default=800.0)
    max_y = max((entity["y"] + entity["h"] for entity in entities.values()), default=600.0)
    if domain_regions:
        max_x = max(max_x, max(region["x"] + region["w"] for region in domain_regions))
        max_y = max(max_y, max(region["y"] + region["h"] for region in domain_regions))

    canvas_w = int(max_x + 120.0)
    canvas_h = int(max_y + 90.0)

    return entities, edges, domain_regions, canvas_w, canvas_h


def build_erd_html(
    table_profiles: List[Dict],
    relationships: List[Dict],
    pk_map: Dict[str, List[str]],
    view_mode: str = "full",
    layout_direction: str = "LR",
    table_order_override: Optional[List[str]] = None,
    domain_hints: Optional[Dict[str, str]] = None,
    fallback_note: str = "",
) -> str:
    direction = "TB" if layout_direction == "TB" else "LR"
    selected_view = "keys" if view_mode == "keys" else "full"

    entities, edges, domain_regions, canvas_w, canvas_h = _build_scene(
        table_profiles,
        relationships,
        pk_map,
        selected_view,
        direction,
        table_order_override=table_order_override,
        domain_hints=domain_hints,
    )

    svg_parts: List[str] = []
    svg_parts.append(
        f'<svg id="erd-svg" xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" viewBox="0 0 {canvas_w} {canvas_h}" role="img" aria-label="Entity relationship diagram">'
    )
    svg_parts.append("<defs>")
    svg_parts.append(
        '<marker id="erd-arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto" markerUnits="strokeWidth"><polygon points="0 0, 8 3, 0 6" fill="#1e3a8a" /></marker>'
    )
    svg_parts.append("</defs>")
    svg_parts.append('<g id="erd-viewport">')

    for region in domain_regions:
        label = html.escape(region["label"])
        domain_class = html.escape(region["domain"])
        svg_parts.append(
            f'<rect class="domain-zone {domain_class}" x="{region["x"]:.1f}" y="{region["y"]:.1f}" width="{region["w"]:.1f}" height="{region["h"]:.1f}" rx="12" ry="12" />'
        )
        svg_parts.append(
            f'<text class="domain-title" x="{region["x"] + 10.0:.1f}" y="{region["y"] + 18.0:.1f}">{label}</text>'
        )

    for edge in edges:
        edge_label = html.escape(edge["label"])
        svg_parts.append(
            f'<path d="{edge["path"]}" class="rel-line" marker-end="url(#erd-arrow)" fill="none" />'
        )
        svg_parts.append(
            f'<text x="{edge["label_x"]:.1f}" y="{edge["label_y"]:.1f}" class="rel-label" text-anchor="middle">{edge_label}</text>'
        )

    for table in sorted(entities.keys()):
        entity = entities[table]
        x = entity["x"]
        y = entity["y"]
        w = entity["w"]
        h = entity["h"]
        cols = entity["columns"]
        title = html.escape(entity["title"])
        header_h = entity.get("header_h", 34)
        row_h = entity.get("row_h", 22)
        dtype_x = entity.get("dtype_x", 12.0)
        name_x = entity.get("name_x", 96.0)
        role_x = entity.get("role_x", w - 10)

        svg_parts.append(f'<g class="entity" transform="translate({x},{y})">')
        svg_parts.append(f'<rect class="entity-body" x="0" y="0" width="{w}" height="{h}" rx="11" ry="11" />')
        svg_parts.append(f'<rect class="entity-head" x="0" y="0" width="{w}" height="{header_h}" rx="11" ry="11" />')
        svg_parts.append(f'<text class="entity-title" x="12" y="22">{title}</text>')

        for idx, col in enumerate(cols):
            y0 = header_h + (idx * row_h)
            y_text = y0 + 15
            dtype = html.escape(col["dtype"])
            col_name = html.escape(col["name"])
            role = html.escape(col["role"])

            if idx > 0:
                svg_parts.append(f'<line class="row-sep" x1="0" y1="{y0}" x2="{w}" y2="{y0}" />')
            svg_parts.append(f'<text class="col-dtype" x="{dtype_x:.1f}" y="{y_text}">{dtype}</text>')
            svg_parts.append(f'<text class="col-name" x="{name_x:.1f}" y="{y_text}">{col_name}</text>')
            if role:
                role_class = "col-role pk" if role == "PK" else "col-role fk"
                svg_parts.append(f'<text class="{role_class}" x="{role_x:.1f}" y="{y_text}" text-anchor="end">{role}</text>')

        svg_parts.append("</g>")

    svg_parts.append("</g>")
    svg_parts.append("</svg>")
    svg_markup = "\n".join(svg_parts)
    escaped_note = html.escape(fallback_note.strip())
    note_html = f'<div class="erd-fallback-note">{escaped_note}</div>' if escaped_note else ""

    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {{
            --bg: #f3f7ff;
            --frame-border: rgba(100, 116, 139, 0.42);
            --grid-line: rgba(148, 163, 184, 0.12);
            --text: #0f172a;
            --muted: #334155;
            --button-bg: #ffffff;
            --button-border: #94a3b8;
            --button-text: #0f172a;
            --head-bg: #dbeafe;
            --head-stroke: #1d4ed8;
            --entity-body: #ffffff;
            --body-stroke: #93c5fd;
            --line: #1e3a8a;
            --line-soft: #cbd5e1;
            --pk: #1d4ed8;
            --fk: #b91c1c;
            --label-stroke: #ffffff;
            --dtype: #475569;
    }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg: #0b1220;
                --frame-border: rgba(148, 163, 184, 0.45);
                --grid-line: rgba(148, 163, 184, 0.11);
                --text: #e2e8f0;
                --muted: #93a6bd;
                --button-bg: #0f172a;
                --button-border: #475569;
                --button-text: #e2e8f0;
                --head-bg: #1d4ed8;
                --head-stroke: #60a5fa;
                --entity-body: #111827;
                --body-stroke: #3b82f6;
                --line: #93c5fd;
                --line-soft: #334155;
                --pk: #93c5fd;
                --fk: #fca5a5;
                --label-stroke: #0b1220;
                --dtype: #cbd5e1;
            }}
        }}
    html, body {{
      margin: 0;
      padding: 0;
      background: var(--bg);
      color: var(--text);
      font-family: 'Space Grotesk', 'Segoe UI', sans-serif;
            overflow: hidden;
    }}
    .erd-shell {{
      width: 100%;
            height: 640px;
                        border: 1px solid var(--frame-border);
            border-radius: 12px;
            background:
                                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px) 0 0 / 24px 24px,
                                linear-gradient(var(--grid-line) 1px, transparent 1px) 0 0 / 24px 24px,
                var(--bg);
      overflow: hidden;
      position: relative;
    }}
    .erd-toolbar {{
      position: absolute;
            top: 10px;
            right: 12px;
      z-index: 2;
      display: flex;
            gap: 6px;
    }}
    .erd-toolbar button {{
            border: 1px solid var(--button-border);
            background: var(--button-bg);
            color: var(--button-text);
            border-radius: 7px;
            min-width: 32px;
            padding: 4px 8px;
      font-size: 12px;
      cursor: pointer;
    }}
    .erd-toolbar button:hover {{
      background: #f1f5f9;
    }}
    .erd-note {{
      position: absolute;
      top: 10px;
      left: 12px;
      z-index: 2;
      font-size: 12px;
            color: var(--muted);
            max-width: 68%;
        }}
        .erd-fallback-note {{
            position: absolute;
            bottom: 10px;
            left: 12px;
            z-index: 2;
            font-size: 11px;
            color: #0f5132;
            background: rgba(220, 252, 231, 0.85);
            border: 1px solid rgba(22, 163, 74, 0.35);
            border-radius: 6px;
            padding: 4px 8px;
    }}
    .erd-canvas {{
      position: absolute;
      inset: 0;
            overflow: hidden;
      cursor: grab;
            user-select: none;
            touch-action: none;
    }}
    .erd-canvas.dragging {{
      cursor: grabbing;
    }}
    .rel-line {{
      stroke: var(--line);
            stroke-width: 1.6;
            opacity: 0.95;
            stroke-linejoin: miter;
    }}
    .rel-label {{
            font-size: 10.5px;
        fill: var(--text);
      paint-order: stroke;
        stroke: var(--label-stroke);
            stroke-width: 2.6;
      stroke-linejoin: round;
    }}
        .domain-zone {{
            stroke-width: 1.1;
        }}
        .domain-zone.sales {{
            fill: rgba(56, 189, 248, 0.08);
            stroke: rgba(2, 132, 199, 0.36);
        }}
        .domain-zone.production {{
            fill: rgba(251, 113, 133, 0.08);
            stroke: rgba(225, 29, 72, 0.36);
        }}
        .domain-zone.core {{
            fill: rgba(34, 197, 94, 0.07);
            stroke: rgba(22, 163, 74, 0.30);
        }}
        .domain-title {{
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.6px;
                        fill: var(--muted);
        }}
    .entity-body {{
            fill: var(--entity-body);
      stroke: var(--body-stroke);
      stroke-width: 1.3;
    }}
    .entity-head {{
      fill: var(--head-bg);
      stroke: var(--head-stroke);
      stroke-width: 1.3;
    }}
    .entity-title {{
      font-size: 13px;
      font-weight: 700;
            fill: var(--text);
      letter-spacing: 0.3px;
    }}
    .row-sep {{
      stroke: var(--line-soft);
      stroke-width: 1;
    }}
    .col-dtype {{
      font-size: 10px;
      font-weight: 700;
            fill: var(--dtype);
    }}
    .col-name {{
      font-size: 11px;
            fill: var(--text);
    }}
    .col-role {{
      font-size: 10px;
      font-weight: 700;
    }}
    .col-role.pk {{ fill: var(--pk); }}
    .col-role.fk {{ fill: var(--fk); }}
  </style>
</head>
<body>
  <div class="erd-shell" id="erd-shell">
    <div class="erd-toolbar">
      <button type="button" onclick="zoomOutErd()">-</button>
      <button type="button" onclick="zoomInErd()">+</button>
      <button type="button" onclick="fitErd()">Fit</button>
      <button type="button" onclick="resetErd()">Reset</button>
    </div>
        <div class="erd-note">Orthogonal routing enabled. Drag to pan, wheel to zoom, use Fit for clean framing.</div>
        {note_html}
    <div class="erd-canvas" id="erd-canvas">
      {svg_markup}
    </div>
  </div>

  <script>
    const shell = document.getElementById('erd-shell');
    const canvas = document.getElementById('erd-canvas');
    const viewport = document.getElementById('erd-viewport');
        const diagramWidth = {canvas_w};
        const diagramHeight = {canvas_h};

    let scale = 1;
        let tx = 0;
        let ty = 0;
    let dragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let startTx = 0;
    let startTy = 0;

        const minScale = 0.25;
    const maxScale = 2.8;

    const applyTransform = () => {{
      viewport.setAttribute('transform', `translate(${{tx}} ${{ty}}) scale(${{scale}})`);
    }};

    const clampScale = (value) => Math.max(minScale, Math.min(maxScale, value));

    window.zoomInErd = () => {{
      scale = clampScale(scale * 1.12);
      applyTransform();
    }};

    window.zoomOutErd = () => {{
      scale = clampScale(scale * 0.89);
      applyTransform();
    }};

    window.resetErd = () => {{
      scale = 1;
            tx = 20;
            ty = 20;
      applyTransform();
    }};

    window.fitErd = () => {{
            const targetW = shell.clientWidth - 24;
            const targetH = shell.clientHeight - 24;
      if (targetW <= 0 || targetH <= 0) return;

            scale = clampScale(Math.min(targetW / diagramWidth, targetH / diagramHeight));
            tx = (shell.clientWidth - (diagramWidth * scale)) / 2;
            ty = (shell.clientHeight - (diagramHeight * scale)) / 2;
      applyTransform();
    }};

    canvas.addEventListener('wheel', (event) => {{
      event.preventDefault();
      const factor = event.deltaY < 0 ? 1.08 : 0.92;
      scale = clampScale(scale * factor);
      applyTransform();
    }}, {{ passive: false }});

    canvas.addEventListener('mousedown', (event) => {{
      dragging = true;
      canvas.classList.add('dragging');
      dragStartX = event.clientX;
      dragStartY = event.clientY;
      startTx = tx;
      startTy = ty;
    }});

    window.addEventListener('mousemove', (event) => {{
      if (!dragging) return;
      tx = startTx + (event.clientX - dragStartX);
      ty = startTy + (event.clientY - dragStartY);
      applyTransform();
    }});

    window.addEventListener('mouseup', () => {{
      dragging = false;
      canvas.classList.remove('dragging');
    }});

        window.addEventListener('resize', () => {{
            fitErd();
        }});

        fitErd();
  </script>
</body>
</html>
"""
