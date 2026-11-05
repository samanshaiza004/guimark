package main

import "core:fmt"
import "core:os"
import "core:time"
import alicorn "alicorn:runtime"

ROOT :: alicorn.Source_Site{"guimark/alicorn", 1, 1, "root"}
ROW  :: alicorn.Source_Site{"guimark/alicorn", 2, 1, "row"}
ROWS :: 10_000

row_labels :: proc(count: int, change_one := -1, change_every := 0) -> [dynamic]string {
	labels := make([dynamic]string, 0, count)
	for i := 0; i < count; i += 1 {
		changed := i == change_one || (change_every > 0 && i % change_every == 0)
		if changed {
			append(&labels, fmt.aprintf("Row %04dX", i/10))
		} else {
			append(&labels, fmt.aprintf("Row %05d", i))
		}
	}
	return labels
}

free_labels :: proc(labels: ^[dynamic]string) {
	for label in labels^ { delete(label) }
	delete(labels^)
}

order_checksum :: proc(count: int, swap_first_two: bool) -> u64 {
	hash: u64 = 0xcbf29ce484222325
	for position := 0; position < count; position += 1 {
		item := position
		if swap_first_two {
			if position == 0 { item = 1 } else if position == 1 { item = 0 }
		}
		hash = (hash ~ u64(item)) * 0x100000001b3
	}
	return hash
}

content_checksum :: proc(labels: []string, swap_first_two: bool) -> u64 {
	hash: u64 = 0xcbf29ce484222325
	for position := 0; position < len(labels); position += 1 {
		item := position
		if swap_first_two {
			if position == 0 { item = 1 } else if position == 1 { item = 0 }
		}
		hash = (hash ~ u64(item)) * 0x100000001b3
		last_byte := labels[item][len(labels[item])-1]
		hash = (hash ~ u64(last_byte)) * 0x100000001b3
	}
	return hash
}

render_tree :: proc(rt: ^alicorn.Runtime, labels: []string, swap_first_two := false) {
	alicorn.invalidate_root(rt, "guimark workload update")
	ui, build := alicorn.begin_frame(rt)
	if !build { return }
	alicorn.container_begin_ex(&ui, .Root, ROOT, label="Guimark", style=alicorn.layout_style(.Column, width=1280, height=900))
	alicorn.container_begin_ex(&ui, .Container, ROW, label="rows", style=alicorn.layout_style(.Column, width=1280, height=900, clip=true))
	for position := 0; position < len(labels); position += 1 {
		item := position
		if swap_first_two {
			if position == 0 { item = 1 } else if position == 1 { item = 0 }
		}
		if alicorn.key_scope_u64(&ui, u64(item), ROW) {
			alicorn.text_ex(&ui, labels[item], ROW)
			alicorn.key_scope_end(&ui)
		}
	}
	alicorn.container_end(&ui)
	alicorn.container_end(&ui)
	alicorn.end_frame(&ui)
}

print_result :: proc(
	workload: string,
	elapsed_ns: i64,
	changed: int,
	labels: []string,
	rt: ^alicorn.Runtime,
	before, after: alicorn.Frame_Stats,
	swap_first_two: bool,
) {
	fmt.printf(
		"{\"schema_version\":1,\"framework\":\"alicorn\",\"framework_version\":\"external-checkout\",\"workload_id\":\"%s\",\"elapsed_ns\":%d,\"logical_items\":%d,\"changed_items\":%d,\"retained_row_nodes\":%d,\"order_checksum\":\"%016x\",\"content_checksum\":\"%016x\",\"diagnostics\":{\"descriptions_emitted\":%d,\"reconcile_nodes_visited\":%d,\"layout_nodes_visited\":%d,\"paint_nodes_visited\":%d,\"nodes_created\":%d,\"nodes_retired\":%d}}\n",
		workload,
		elapsed_ns,
		ROWS,
		changed,
		len(rt.nodes)-2,
		order_checksum(ROWS, swap_first_two),
		content_checksum(labels, swap_first_two),
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
	if workload != "tree.construct.10000" && workload != "tree.update.one.10000" && workload != "tree.update.ten_percent.10000" && workload != "tree.reorder.swap_adjacent.10000" {
		fmt.eprintln("unknown workload: ", workload)
		os.exit(2)
	}

	base := row_labels(ROWS)
	one_changed := row_labels(ROWS, change_one=5000)
	ten_percent := row_labels(ROWS, change_every=10)
	defer free_labels(&base)
	defer free_labels(&one_changed)
	defer free_labels(&ten_percent)

	rt := alicorn.new_runtime(alicorn.Rect{0, 0, 1280, 900})
	defer alicorn.destroy_runtime(&rt)
	if !alicorn.text_engine_load_font(&rt.text_engine, #load("../../assets/fonts/AtkinsonHyperlegibleNext-Variable.ttf")) {
		fmt.eprintln("could not load Guimark shared font")
		os.exit(1)
	}

	changed := 0
	swap := false
	measure_labels := base[:]
	if workload == "tree.construct.10000" {
		// The first completed frame measures initial tree construction.
	} else {
		render_tree(&rt, base[:])
		if workload == "tree.update.one.10000" {
			measure_labels = one_changed[:]
			changed = 1
		} else if workload == "tree.update.ten_percent.10000" {
			measure_labels = ten_percent[:]
			changed = ROWS / 10
		} else {
			swap = true
		}
	}

	before := rt.stats
	start := time.now()
	render_tree(&rt, measure_labels, swap)
	elapsed_ns := time.duration_nanoseconds(time.since(start))
	after := rt.stats
	print_result(workload, elapsed_ns, changed, measure_labels, &rt, before, after, swap)
}
