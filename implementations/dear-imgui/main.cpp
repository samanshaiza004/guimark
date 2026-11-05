#include "imgui.h"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <utility>
#include <vector>

namespace {
constexpr int kRows = 10'000;
constexpr float kWidth = 1280.0f;
constexpr float kHeight = 900.0f;
constexpr std::uint64_t kFnvOffset = 0xcbf29ce484222325ULL;
constexpr std::uint64_t kFnvPrime = 0x100000001b3ULL;

void hash_u64(std::uint64_t& hash, std::uint64_t value) {
    hash = (hash ^ value) * kFnvPrime;
}

void hash_text(std::uint64_t& hash, const std::string& value) {
    for (unsigned char byte : value) hash_u64(hash, byte);
    hash_u64(hash, 0xff);
}

void hash_float(std::uint64_t& hash, float value) {
    std::uint32_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    hash_u64(hash, bits);
}

std::vector<std::string> make_labels(int change_one = -1, int change_every = 0) {
    std::vector<std::string> labels;
    labels.reserve(kRows);
    for (int i = 0; i < kRows; ++i) {
        char buffer[32];
        const bool changed = i == change_one || (change_every > 0 && i % change_every == 0);
        if (changed) std::snprintf(buffer, sizeof(buffer), "Row %04dX", i / 10);
        else std::snprintf(buffer, sizeof(buffer), "Row %05d", i);
        labels.emplace_back(buffer);
    }
    return labels;
}

std::vector<int> make_order(bool swap_first_two) {
    std::vector<int> order(kRows);
    for (int i = 0; i < kRows; ++i) order[i] = i;
    if (swap_first_two) std::swap(order[0], order[1]);
    return order;
}

struct FrameOutput {
    std::uint64_t order_hash = kFnvOffset;
    std::uint64_t content_hash = kFnvOffset;
    std::uint64_t draw_hash = kFnvOffset;
    int submitted_rows = 0;
    int visible_rows = 0;
    int draw_vertices = 0;
    int draw_indices = 0;
    int draw_commands = 0;
};

std::uint64_t draw_data_checksum(const ImDrawData* draw_data) {
    std::uint64_t hash = kFnvOffset;
    hash_u64(hash, static_cast<std::uint64_t>(draw_data->TotalVtxCount));
    hash_u64(hash, static_cast<std::uint64_t>(draw_data->TotalIdxCount));
    hash_u64(hash, static_cast<std::uint64_t>(draw_data->CmdLists.Size));
    hash_float(hash, draw_data->DisplayPos.x);
    hash_float(hash, draw_data->DisplayPos.y);
    hash_float(hash, draw_data->DisplaySize.x);
    hash_float(hash, draw_data->DisplaySize.y);
    hash_float(hash, draw_data->FramebufferScale.x);
    hash_float(hash, draw_data->FramebufferScale.y);
    for (int list_index = 0; list_index < draw_data->CmdLists.Size; ++list_index) {
        const ImDrawList* list = draw_data->CmdLists[list_index];
        hash_u64(hash, static_cast<std::uint64_t>(list->VtxBuffer.Size));
        hash_u64(hash, static_cast<std::uint64_t>(list->IdxBuffer.Size));
        hash_u64(hash, static_cast<std::uint64_t>(list->CmdBuffer.Size));
        for (int i = 0; i < list->VtxBuffer.Size; ++i) {
            const ImDrawVert& vertex = list->VtxBuffer[i];
            hash_float(hash, vertex.pos.x);
            hash_float(hash, vertex.pos.y);
            hash_float(hash, vertex.uv.x);
            hash_float(hash, vertex.uv.y);
            hash_u64(hash, vertex.col);
        }
        for (int i = 0; i < list->IdxBuffer.Size; ++i)
            hash_u64(hash, list->IdxBuffer[i]);
        for (int i = 0; i < list->CmdBuffer.Size; ++i) {
            const ImDrawCmd& command = list->CmdBuffer[i];
            hash_float(hash, command.ClipRect.x);
            hash_float(hash, command.ClipRect.y);
            hash_float(hash, command.ClipRect.z);
            hash_float(hash, command.ClipRect.w);
            hash_u64(hash, command.ElemCount);
            hash_u64(hash, command.IdxOffset);
            hash_u64(hash, command.VtxOffset);
            hash_u64(hash, command.UserCallback != nullptr);
        }
    }
    return hash;
}

void begin_scene() {
    ImGui::NewFrame();
    ImGui::SetNextWindowPos(ImVec2(0, 0), ImGuiCond_Always);
    ImGui::SetNextWindowSize(ImVec2(kWidth, kHeight), ImGuiCond_Always);
    constexpr ImGuiWindowFlags flags = ImGuiWindowFlags_NoDecoration |
        ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoResize |
        ImGuiWindowFlags_NoSavedSettings;
    ImGui::Begin("Guimark", nullptr, flags);
    ImGui::BeginChild("rows", ImVec2(kWidth, kHeight), ImGuiChildFlags_None,
                      ImGuiWindowFlags_NoScrollbar | ImGuiWindowFlags_NoScrollWithMouse);
}

void end_scene() {
    ImGui::EndChild();
    ImGui::End();
    ImGui::Render();
}

void draw_tree(const std::vector<std::string>& labels,
               const std::vector<int>& order) {
    begin_scene();
    for (int item : order)
        ImGui::TextUnformatted(labels[item].c_str());
    end_scene();
}

FrameOutput validate_tree(const std::vector<std::string>& labels,
                          const std::vector<int>& order) {
    FrameOutput output;
    begin_scene();
    ImDrawList* row_draw_list = ImGui::GetWindowDrawList();
    for (int item : order) {
        hash_u64(output.order_hash, static_cast<std::uint64_t>(item));
        hash_text(output.content_hash, labels[item]);
        ++output.submitted_rows;
        const int vertices_before = row_draw_list->VtxBuffer.Size;
        ImGui::TextUnformatted(labels[item].c_str());
        if (row_draw_list->VtxBuffer.Size > vertices_before)
            ++output.visible_rows;
    }
    end_scene();
    const ImDrawData* draw_data = ImGui::GetDrawData();
    output.draw_hash = draw_data_checksum(draw_data);
    output.draw_vertices = draw_data->TotalVtxCount;
    output.draw_indices = draw_data->TotalIdxCount;
    for (int i = 0; i < draw_data->CmdLists.Size; ++i)
        output.draw_commands += draw_data->CmdLists[i]->CmdBuffer.Size;
    return output;
}
void print_result(const char* workload, long long elapsed_ns, int changed,
                  const FrameOutput& output, const FrameOutput* baseline) {
    char baseline_text[32] = "null";
    if (baseline != nullptr)
        std::snprintf(baseline_text, sizeof(baseline_text), "\"%016llx\"",
                      static_cast<unsigned long long>(baseline->draw_hash));
    std::printf(
        "{\"schema_version\":1,\"framework\":\"dear-imgui\",\"framework_version\":\"%s\",\"workload_id\":\"%s\",\"elapsed_ns\":%lld,\"logical_items\":%d,\"changed_items\":%d,\"order_checksum\":\"%016llx\",\"output_validation\":{\"submitted_rows\":%d,\"visible_rows\":%d,\"content_checksum\":\"%016llx\",\"rendered_output_checksum\":\"%016llx\",\"baseline_rendered_output_checksum\":%s,\"rendered_output_kind\":\"dear-imgui-draw-data\"},\"diagnostics\":{\"draw_vertices\":%d,\"draw_indices\":%d,\"draw_commands\":%d,\"submitted_text_calls\":%d}}\n",
        IMGUI_VERSION, workload, elapsed_ns, kRows, changed,
        static_cast<unsigned long long>(output.order_hash), output.submitted_rows,
        output.visible_rows, static_cast<unsigned long long>(output.content_hash),
        static_cast<unsigned long long>(output.draw_hash), baseline_text,
        output.draw_vertices, output.draw_indices, output.draw_commands,
        output.submitted_rows);
}
} // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::fprintf(stderr, "usage: guimark-imgui <workload-id>\n");
        return 2;
    }
    const char* workload = argv[1];
    const bool construction = std::strcmp(workload, "tree.construct.10000") == 0;
    const bool one_visible = std::strcmp(workload, "tree.update.one.visible.10000") == 0;
    const bool one_offscreen = std::strcmp(workload, "tree.update.one.offscreen.10000") == 0;
    const bool ten_percent = std::strcmp(workload, "tree.update.ten_percent.10000") == 0;
    const bool reorder = std::strcmp(workload, "tree.reorder.text_order.swap_adjacent.10000") == 0;
    if (!(construction || one_visible || one_offscreen || ten_percent || reorder)) {
        std::fprintf(stderr, "unknown workload: %s\n", workload);
        return 2;
    }

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.IniFilename = nullptr;
    io.DisplaySize = ImVec2(kWidth, kHeight);
    io.DisplayFramebufferScale = ImVec2(1, 1);
    io.DeltaTime = 1.0f / 60.0f;
    ImGuiStyle& style = ImGui::GetStyle();
    style.WindowPadding = ImVec2(0, 0);
    style.WindowBorderSize = 0;
    style.ChildBorderSize = 0;
    style.FramePadding = ImVec2(0, 0);
    style.ItemSpacing = ImVec2(0, 4);
    style.ItemInnerSpacing = ImVec2(0, 0);
    const char* font_path = std::getenv("GUIMARK_FONT");
    if (font_path == nullptr || io.Fonts->AddFontFromFileTTF(font_path, 16.0f) == nullptr) {
        std::fprintf(stderr, "set GUIMARK_FONT to the Guimark shared font file\n");
        ImGui::DestroyContext();
        return 1;
    }
    if (!io.Fonts->Build()) {
        std::fprintf(stderr, "could not build Dear ImGui font atlas\n");
        ImGui::DestroyContext();
        return 1;
    }

    const auto base = make_labels();
    auto one_visible_changed = base;
    one_visible_changed[10].back() = 'X';
    auto one_offscreen_changed = base;
    one_offscreen_changed[5000].back() = 'X';
    const auto ten_percent_changed = make_labels(-1, 10);
    const auto base_order = make_order(false);
    const auto reordered = make_order(true);
    const std::vector<std::string>* measured = &base;
    const std::vector<int>* order = reorder ? &reordered : &base_order;
    int changed = 0;
    if (one_visible) { measured = &one_visible_changed; changed = 1; }
    else if (one_offscreen) { measured = &one_offscreen_changed; changed = 1; }
    else if (ten_percent) { measured = &ten_percent_changed; changed = kRows / 10; }

    FrameOutput baseline_output;
    bool has_baseline = false;
    if (!construction) {
        baseline_output = validate_tree(base, base_order);
        has_baseline = true;
    }
    const auto start = std::chrono::steady_clock::now();
    draw_tree(*measured, *order);
    const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - start).count();
    const FrameOutput output = validate_tree(*measured, *order);
    if (output.submitted_rows != kRows || output.visible_rows != 45) {
        std::fprintf(stderr, "Dear ImGui output invariant failed: submitted=%d visible=%d\n",
                     output.submitted_rows, output.visible_rows);
        ImGui::DestroyContext();
        return 1;
    }
    print_result(workload, elapsed, changed, output,
                 has_baseline ? &baseline_output : nullptr);
    ImGui::DestroyContext();
    return 0;
}
