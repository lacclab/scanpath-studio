import torch
from torchvision.transforms import GaussianBlur, Resize

max_x = 2560
max_y = 1440
row_hight_in_pxl = 111

gaussian_blur = GaussianBlur(kernel_size=51, sigma=10)
resize_func_1 = Resize((512, 512))
resize_func_2 = Resize((128, 128))

device = "cuda:6"

# tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
# model = GPT2Model.from_pretrained("gpt2").to(device)
# word_embd_dim = model.config.hidden_size


def resize_and_blur(X: torch.tensor):
    X = resize_func_1(X)
    X = gaussian_blur(X)
    X = resize_func_2(X)
    return X


def calc_fix_heatmaps_df(df):
    #!
    prelim_RT_heatmap = torch.zeros((max_y, max_x)).to(device)
    prelim_time_heatmap = (torch.zeros((max_y, max_x)) - 1).to(device)

    acc_time = 0
    for x, y, fix_dur, next_sacc_dur in list(
        df[
            [
                "CURRENT_FIX_X",
                "CURRENT_FIX_Y",
                "CURRENT_FIX_DURATION",
                "NEXT_SAC_DURATION",
            ]
        ].values
    ):
        prelim_RT_heatmap[y, x] = fix_dur  #! [y, x] is not a mistake. Think about it

        acc_time += fix_dur + next_sacc_dur
        prelim_time_heatmap[y, x] = acc_time

    # smooth the heatmap using a gaussian kernel
    RT_heatmap = resize_and_blur(prelim_RT_heatmap.unsqueeze(0)).squeeze(0)
    time_heatmap = resize_and_blur(prelim_time_heatmap.unsqueeze(0)).squeeze(0)

    return RT_heatmap, time_heatmap


def calc_ia_text_meatmap(ia_rep):
    # text_lst = ia_rep["IA_LABEL"].tolist()
    # text = " ".join(text_lst)

    skipping_binary_heatmap = torch.zeros((max_y, max_x))

    # word_embd_tensor = torch.zeros((max_y, max_x, word_embd_dim))

    for i, (y, x, is_skipped) in enumerate(
        ia_rep[["IA_TOP", "IA_LEFT", "IA_SKIP"]].values
    ):
        # word_embd_tensor[y + round(row_hight_in_pxl / 2), x] = embeddings[i]
        skipping_binary_heatmap[y + row_hight_in_pxl, x] = is_skipped

    # # apply a gaussian filter to the embeddings and resize them to 256x256
    # tensor_embd_dim_first = torch.transpose(word_embd_tensor, 0, 2).to("cuda:6")
    # # apply on each dimension separately
    # tensor_embd_dim_first = resize_and_blur(tensor_embd_dim_first)
    # # transpose back
    # embd_dim_first_tensor = torch.transpose(tensor_embd_dim_first, 0, 2)
    # # make it a sparse tensor
    # embd_dim_first_tensor_sparse = embd_dim_first_tensor.to_sparse()

    skipping_binary_heatmap = resize_and_blur(
        skipping_binary_heatmap.unsqueeze(0)
    ).squeeze(0)

    return skipping_binary_heatmap
    # return embd_dim_first_tensor_sparse, skipping_binary_heatmap


def calc_heatmaps_df(ia_rep, fix_rep):
    fix_heatmaps_df = (
        fix_rep.groupby(["subject_id", "unique_paragraph_id", "reread"])
        .apply(calc_fix_heatmaps_df)
        .reset_index()
        .rename(columns={0: "heatmaps"})
    )

    ia_heatmaps_df = (
        ia_rep.groupby(["subject_id", "unique_paragraph_id", "reread"])
        .apply(calc_ia_text_meatmap)
        .reset_index()
        .rename(columns={0: "heatmaps"})
    )

    # break the heatmaps into two columns
    fix_heatmaps_df["RT_heatmap"] = fix_heatmaps_df["heatmaps"].apply(lambda x: x[0])
    fix_heatmaps_df["time_heatmap"] = fix_heatmaps_df["heatmaps"].apply(lambda x: x[1])

    # ia_heatmaps_df["text_embd_heatmap"] = ia_heatmaps_df["heatmaps"].apply(
    #     lambda x: x[0]
    # )
    # ia_heatmaps_df["skipping_binary_heatmap"] = ia_heatmaps_df["heatmaps"].apply(
    #     lambda x: x[1]
    # )

    ia_heatmaps_df["skipping_binary_heatmap"] = ia_heatmaps_df["heatmaps"].apply(
        lambda x: x
    )

    heatmaps_df = fix_heatmaps_df.drop(columns=["heatmaps"]).merge(
        ia_heatmaps_df.drop(columns=["heatmaps"]),
        on=["subject_id", "unique_paragraph_id", "reread"],
        how="inner",
    )

    return heatmaps_df


train_heatmaps_df = calc_heatmaps_df(train_df_ia, train_df_fix)
