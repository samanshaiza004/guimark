package main

import "core:fmt"
import "core:os"
import "core:time"
import alicorn "alicorn:runtime"

ROOT :: alicorn.Source_Site{"guimark/alicorn", 1, 1, "root"}
ROW  :: alicorn.Source_Site{"guimark/alicorn", 2, 1, "row"}
ROWS :: 10_000
VIEW_WIDTH :: f32(1280)
VIEW_HEIGHT :: f32(900)
ROW_PITCH :: f32(20)
FONT_SIZE :: f32(16)

row_labels :: proc(count: int, change_one := -1, change_every := 0) -> [dynamic]string {
	labels := make([dynamic]string, 0, count)
	for i := 0; i < count; i += 1 {
		changed := i == change_one || (change_every > 0 && i % change_every == 0)
		if changed { append(&labels, fmt.aprintf("Row %04dX", i/10)) }
		else { append(&labels, fmt.aprintf("Row %05d", i)) }
	}
	return labels
}

free_labels :: proc(labels: ^[dynamic]string) {
	for label in labels^ { delete(label) }
	delete(labels^)
}

fnv_u64 :: proc(hash, value: u64) -> u64 { return (hash ~ value) * 0x100000001b3 }

fnv_text :: proc(hash: u64, value: string) -> u64 {
	result := hash
	for index := 0; index < len(value); index += 1 { result = fnv_u64(result, u64(value[index])) }
	return fnv_u64(result, 0xff)
}

fnv_f32 :: proc(hash: u64, value: f32) -> u64 {
	bits := transmute(u32)value
	return fnv_u64(hash, u64(bits))
}

fnv_rect :: proc(hash: u64, rect: alicorn.Rect) -> u64 {
	result := fnv_f32(hash, rect.x)
	result = fnv_f32(result, rect.y)
	result = fnv_f32(result, rect.w)
	return fnv_f32(result, rect.h)
}

render_tree :: proc(rt: ^alicorn.Runtime, labels: []string, swap_first_two := false) -> alicorn.Node_ID {
	alicorn.invalidate_root(rt, "guimark workload update")
	ui, build := alicorn.begin_frame(rt)
	if !build { return 0 }
	alicorn.container_begin_ex(&ui, .Root, ROOT, label="Guimark", style=alicorn.layout_style(.Column, width=VIEW_WIDTH, height=VIEW_HEIGHT))
	rows_id := alicorn.container_begin_ex(&ui, .Container, ROW, label="rows", style=alicorn.layout_style(.Column, width=VIEW_WIDTH, height=VIEW_HEIGHT, clip=true))
	for position := 0; position < len(labels); position += 1 {
		item := position
		if swap_first_two {
			if position == 0 { item = 1 } else if position == 1 { item = 0 }
		}
		if alicorn.key_scope_u64(&ui, u64(item), ROW) {
			alicorn.text_ex(&ui, labels[item], ROW,
				style=alicorn.layout_style(.Column, width=VIEW_WIDTH, height=ROW_PITCH),
				text_style=alicorn.Text_Style{font_weight=alicorn.FONT_WEIGHT_REGULAR, font_size=FONT_SIZE, overflow=.Clip})
			alicorn.key_scope_end(&ui)
		}
	}
	alicorn.container_end(&ui)
	alicorn.container_end(&ui)
	alicorn.end_frame(&ui)
	return rows_id
}

rects_intersect :: proc(a, b: alicorn.Rect) -> bool {
	return min(a.x+a.w, b.x+b.w) > max(a.x,b.x) && min(a.y+a.h, b.y+b.h) > max(a.y,b.y)
}

Output_Validation :: struct {
	submitted_rows: int,
	visible_rows: int,
	order_checksum: u64,
	content_checksum: u64,
	rendered_output_checksum: u64,
}

validate_output :: proc(
	rt: ^alicorn.Runtime,
	rows_id: alicorn.Node_ID,
	baseline_ids: []alicorn.Node_ID,
	labels: []string,
	swap_first_two: bool,
) -> (output: Output_Validation, valid: bool) {
	rows, found := rt.nodes[rows_id]
	if !found || rows == nil || len(rows.children) != ROWS || len(baseline_ids) != ROWS { return {}, false }
	identity_index := make(map[alicorn.Node_ID]int, allocator=rt.scratch_allocator)
	for index, id in baseline_ids { identity_index[id] = index }
	row_nodes := make(map[alicorn.Node_ID]^alicorn.Node, allocator=rt.scratch_allocator)
	output.content_checksum = 0xcbf29ce484222325
	order_hash: u64 = 0xcbf29ce484222325
	for position, id in rows.children {
		node, exists := rt.nodes[id]
		if !exists || node == nil || node.kind != .Text { return {}, false }
		item, identity_found := identity_index[id]
		if !identity_found { return {}, false }
		expected_item := position
		if swap_first_two {
			if position == 0 { expected_item = 1 } else if position == 1 { expected_item = 0 }
		}
		if item != expected_item || node.text != labels[expected_item] { return {}, false }
		order_hash = fnv_u64(order_hash, u64(item))
		output.content_checksum = fnv_text(output.content_checksum, node.text)
		row_nodes[id] = node
	}
	output.submitted_rows = len(rows.children)
	output.order_checksum = order_hash
	output.rendered_output_checksum = 0xcbf29ce484222325
	visible := make(map[alicorn.Node_ID]bool, allocator=rt.scratch_allocator)
	for command in rt.display {
		paint, is_text := command.payload.(alicorn.Text_Paint)
		if !is_text { continue }
		node, is_row := row_nodes[command.owner]
		if !is_row { continue }
		run, resolved := alicorn.paint_text_run_resolve(rt, paint.run)
		if !resolved || run.value != node.text { return {}, false }
		if !rects_intersect(command.bounds, command.clip) { continue }
		if !visible[command.owner] {
			visible[command.owner] = true
			output.rendered_output_checksum = fnv_u64(output.rendered_output_checksum, u64(command.owner))
			output.rendered_output_checksum = fnv_text(output.rendered_output_checksum, run.value)
			output.rendered_output_checksum = fnv_rect(output.rendered_output_checksum, command.bounds)
			output.rendered_output_checksum = fnv_rect(output.rendered_output_checksum, command.clip)
		}
	}
	output.visible_rows = len(visible)
	return output, order_hash == expected_order_checksum(swap_first_two)
}

expected_order_checksum :: proc(swap_first_two: bool) -> u64 {
	hash: u64 = 0xcbf29ce484222325
	for position := 0; position < ROWS; position += 1 {
		item := position
		if swap_first_two {
			if position == 0 { item = 1 } else if position == 1 { item = 0 }
		}
		hash = fnv_u64(hash, u64(item))
	}
	return hash
}

snapshot_ids :: proc(rt: ^alicorn.Runtime, rows_id: alicorn.Node_ID) -> (ids: [dynamic]alicorn.Node_ID, valid: bool) {
	rows, found := rt.nodes[rows_id]
	if !found || rows == nil || len(rows.children) != ROWS { return nil, false }
	ids = make([dynamic]alicorn.Node_ID, 0, ROWS)
	for id in rows.children { append(&ids, id) }
	return ids, true
}

print_result :: proc(
	workload: string,
	elapsed_ns: i64,
	changed: int,
	output: Output_Validation,
	baseline_checksum: string,
	rt: ^alicorn.Runtime,
	before, after: alicorn.Frame_Stats,
) {
	fmt.printf(
		"{\"schema_version\":1,\"framework\":\"alicorn\",\"framework_version\":\"external-checkout\",\"workload_id\":\"%s\",\"elapsed_ns\":%d,\"logical_items\":%d,\"changed_items\":%d,\"retained_row_nodes\":%d,\"order_checksum\":\"%016x\",\"output_validation\":{\"submitted_rows\":%d,\"visible_rows\":%d,\"content_checksum\":\"%016x\",\"rendered_output_checksum\":\"%016x\",\"baseline_rendered_output_checksum\":%s,\"rendered_output_kind\":\"alicorn-text-paint-display-list\"},\"diagnostics\":{\"descriptions_emitted\":%d,\"reconcile_nodes_visited\":%d,\"layout_nodes_visited\":%d,\"paint_nodes_visited\":%d,\"nodes_created\":%d,\"nodes_retired\":%d}}\n",
		workload, elapsed_ns, ROWS, changed, output.submitted_rows, output.order_checksum,
		output.submitted_rows, output.visible_rows, output.content_checksum, output.rendered_output_checksum, baseline_checksum,
		after.descriptions_emitted-before.descriptions_emitted,
		after.reconcile_nodes_visited-before.reconcile_nodes_visited,
		after.layout_nodes_visited-before.layout_nodes_visited,
		after.paint_nodes_visited-before.paint_nodes_visited,
		after.nodes_created-before.nodes_created,
		after.nodes_retired-before.nodes_retired,
	)
}

main :: proc() {
	if len(os.args) != 2 {
		fmt.eprintln("usage: guimark-alicorn <workload-id>")
		os.exit(2)
	}
	workload := os.args[1]
	if workload != "tree.construct.10000" && workload != "tree.update.one.visible.10000" && workload != "tree.update.one.offscreen.10000" && workload != "tree.update.ten_percent.10000" && workload != "tree.reorder.text_order.swap_adjacent.10000" {
		fmt.eprintln("unknown workload: ", workload)
		os.exit(2)
	}

	base := row_labels(ROWS)
	one_visible := row_labels(ROWS, change_one=10)
	one_offscreen := row_labels(ROWS, change_one=5000)
	ten_percent := row_labels(ROWS, change_every=10)
	defer free_labels(&base)
	defer free_labels(&one_visible)
	defer free_labels(&one_offscreen)
	defer free_labels(&ten_percent)

	rt := alicorn.new_runtime(alicorn.Rect{0, 0, VIEW_WIDTH, VIEW_HEIGHT})
	defer alicorn.destroy_runtime(&rt)
	if !alicorn.text_engine_load_font(&rt.text_engine, #load("../../assets/fonts/AtkinsonHyperlegibleNext-Variable.ttf")) {
		fmt.eprintln("could not load Guimark shared font")
		os.exit(1)
	}

	changed := 0
	swap := workload == "tree.reorder.text_order.swap_adjacent.10000"
	measure_labels := base[:]
	var rows_id: alicorn.Node_ID
	var baseline_ids: [dynamic]alicorn.Node_ID
	defer delete(baseline_ids)
	baseline_checksum := "null"
	if workload != "tree.construct.10000" {
		rows_id = render_tree(&rt, base[:])
		var good: bool
		baseline_ids, good = snapshot_ids(&rt, rows_id)
		if !good { fmt.eprintln("could not inspect Alicorn baseline row tree"); os.exit(1) }
		baseline, baseline_ok := validate_output(&rt, rows_id, baseline_ids[:], base[:], false)
		if !baseline_ok || baseline.visible_rows != 45 { fmt.eprintln("Alicorn baseline retained/output invariant failed"); os.exit(1) }
		baseline_checksum = fmt.aprintf("\"%016x\"", baseline.rendered_output_checksum)
		if workload == "tree.update.one.visible.10000" { measure_labels = one_visible[:]; changed = 1 }
		else if workload == "tree.update.one.offscreen.10000" { measure_labels = one_offscreen[:]; changed = 1 }
		else if workload == "tree.update.ten_percent.10000" { measure_labels = ten_percent[:]; changed = ROWS/10 }
	}

	before := rt.stats
	start := time.now()
	rows_id = render_tree(&rt, measure_labels, swap)
	elapsed_ns := time.duration_nanoseconds(time.since(start))
	after := rt.stats
	if workload == "tree.construct.10000" {
		var good: bool
		baseline_ids, good = snapshot_ids(&rt, rows_id)
		if !good { fmt.eprintln("could not inspect Alicorn constructed row tree"); os.exit(1) }
	}
	output, output_ok := validate_output(&rt, rows_id, baseline_ids[:], measure_labels, swap)
	if !output_ok || output.visible_rows != 45 {
		fmt.eprintln("Alicorn retained node identity/order or text paint output invariant failed")
		os.exit(1)
	}
	print_result(workload, elapsed_ns, changed, output, baseline_checksum, &rt, before, after)
}
