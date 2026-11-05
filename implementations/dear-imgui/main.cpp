#include "imgui.h"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>

namespace {
constexpr int kRows = 10'000;
constexpr std::uint64_t kFnvOffset = 0xcbf29ce484222325ULL;
constexpr std::uint64_t kFnvPrime = 0x100000001b3ULL;

std::uint64_t order_checksum(bool swap_first_two) {
    std::uint64_t hash = kFnvOffset;
    for (int position = 0; position < kRows; ++position) {
        int item = position;
        if (swap_first_two) {
            if (position == 0) item = 1;
            else if (position == 1) item = 0;
        }
        hash = (hash ^ static_cast<std::uint64_t>(item)) * kFnvPrime;
    }
    return hash;
}

std::uint64_t content_checksum(const std::vector<std::string>& labels, bool swap_first_two) {
    std::uint64_t hash = kFnvOffset;
    for (int position = 0; position < kRows; ++position) {
        int item = position;
        if (swap_first_two) {
            if (position == 0) item = 1;
            else if (position == 1) item = 0;
        }
        hash = (hash ^ static_cast<std::uint64_t>(item)) * kFnvPrime;
        hash = (hash ^ static_cast<unsigned char>(labels[item].back())) * kFnvPrime;
    }
    return hash;
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

void draw_tree(const std::vector<std::string>& labels, bool swap_first_two) {
    ImGui::NewFrame();
    ImGui::SetNextWindowPos(ImVec2(0, 0), ImGuiCond_Always);
    ImGui::SetNextWindowSize(ImVec2(1280, 900), ImGuiCond_Always);
    constexpr ImGuiWindowFlags flags = ImGuiWindowFlags_NoDecoration |
        ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoResize |
        ImGuiWindowFlags_NoSavedSettings;
    ImGui::Begin("Guimark", nullptr, flags);
    ImGui::BeginChild("rows", ImVec2(0, 0), ImGuiChildFlags_None);
    for (int position = 0; position < kRows; ++position) {
        int item = position;
        if (swap_first_two) {
            if (position == 0) item = 1;
            else if (position == 1) item = 0;
        }
        ImGui::PushID(item);
        ImGui::TextUnformatted(labels[item].c_str());
        ImGui::PopID();
    }
    ImGui::EndChild();
    ImGui::End();
    ImGui::Render();
}

void print_result(const char* workload, long long elapsed_ns, int changed,
                  const std::vector<std::string>& labels, bool swap_first_two) {
    std::printf(
        "{\"schema_version\":1,\"framework\":\"dear-imgui\",\"framework_version\":\"%s\",\"workload_id\":\"%s\",\"elapsed_ns\":%lld,\"logical_items\":%d,\"changed_items\":%d,\"retained_row_nodes\":%d,\"order_checksum\":\"%016llx\",\"content_checksum\":\"%016llx\",\"diagnostics\":{\"draw_vertices\":%d,\"draw_commands\":%d}}\n",
        IMGUI_VERSION, workload, elapsed_ns, kRows, changed, 0,
        static_cast<unsigned long long>(order_checksum(swap_first_two)),
        static_cast<unsigned long long>(content_checksum(labels, swap_first_two)),
        ImGui::GetDrawData()->TotalVtxCount, ImGui::GetDrawData()->CmdLists.Size);
}
} // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::fprintf(stderr, "usage: guimark-imgui <workload-id>\n");
        return 2;
    }
    const char* workload = argv[1];
    const bool construction = std::strcmp(workload, "tree.construct.10000") == 0;
    const bool one_update = std::strcmp(workload, "tree.update.one.10000") == 0;
    const bool ten_percent = std::strcmp(workload, "tree.update.ten_percent.10000") == 0;
    const bool reorder = std::strcmp(workload, "tree.reorder.swap_adjacent.10000") == 0;
    if (!(construction || one_update || ten_percent || reorder)) {
        std::fprintf(stderr, "unknown workload: %s\n", workload);
        return 2;
    }

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.IniFilename = nullptr;
    io.DisplaySize = ImVec2(1280, 900);
    io.DisplayFramebufferScale = ImVec2(1, 1);
    io.DeltaTime = 1.0f / 60.0f;
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
    auto one_changed = base;
    one_changed[5000].back() = 'X';
    const auto ten_percent_changed = make_labels(-1, 10);
    const std::vector<std::string>* measured = &base;
    int changed = 0;
    bool swap = false;
    if (one_update) {
        measured = &one_changed;
        changed = 1;
    } else if (ten_percent) {
        measured = &ten_percent_changed;
        changed = kRows / 10;
    } else if (reorder) {
        swap = true;
    }

    if (!construction) draw_tree(base, false);
    const auto start = std::chrono::steady_clock::now();
    draw_tree(*measured, swap);
    const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - start).count();
    print_result(workload, elapsed, changed, *measured, swap);
    ImGui::DestroyContext();
    return 0;
}
