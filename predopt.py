import gc

import numpy as np
import torch
from sklearn.metrics import mean_absolute_error
from tqdm.notebook import tqdm

true_constants_SVWN = [
    0.0310907,
    0.01554535,
    3.72744,
    7.06042,
    12.9352,
    18.0578,
    -0.10498,
    -0.32500,
    0.0310907,
    0.01554535,
    -1 / (6 * np.pi**2),
    13.0720,
    20.1231,
    1.06835,
    42.7198,
    101.578,
    11.4813,
    -0.409286,
    -0.743294,
    -0.228344,
    1,
]

true_constants_PBE = torch.Tensor(
    [
        [
            0.06672455060314922,
            (1 - torch.log(torch.Tensor([2]))) / (np.pi**2),
            1.709921,
            7.5957,
            14.1189,
            10.357,
            3.5876,
            6.1977,
            3.6231,
            1.6382,
            3.3662,
            0.88026,
            0.49294,
            0.62517,
            0.49671,
            # 1,  1,  1,
            0.031091,
            0.015545,
            0.016887,
            0.21370,
            0.20548,
            0.11125,
            -3 / 8 * (3 / np.pi) ** (1 / 3) * 4 ** (2 / 3),
            0.8040,
            0.2195149727645171,
            0.8040,
            0.2195149727645171,
        ]
    ]
)


class DatasetPredopt(torch.utils.data.Dataset):
    def __init__(self, data, dft):
        self.data = data
        self.dft = dft

    def __getitem__(self, i):
        self.data[i].pop("Database", None)
        if self.dft == "PBE":
            y_single = true_constants_PBE
        elif self.dft == "SVWN3":
            y_single = true_constants_SVWN
        elif self.dft == "XALPHA":
            y_single = torch.Tensor([1.05])
        return self.data[i], y_single

    def __len__(self):
        return len(self.data.keys())


def predopt(
    model, criterion, optimizer, train_loader, device, n_epochs=2, accum_iter=1, double_star=False, xalpha=False
):
    train_loss_mse = []
    train_loss_mae = []

    for epoch in range(n_epochs):
        print("Epoch", epoch + 1)
        model.train()

        train_mse_losses_per_epoch = []
        train_mae_losses_per_epoch = []

        progress_bar = tqdm(train_loader)

        for batch_idx, (X_batch, y_batch) in enumerate(progress_bar):
            X_batch = X_batch["Grid"].to(device, non_blocking=True)
            if not double_star and not xalpha:
                y_batch = torch.tile(y_batch, [X_batch.shape[0], 1]).to(
                    device, non_blocking=True
                )[
                    :, [0, 1, 22, 23, 24, 25]
                ]
                predictions = model(X_batch)[:, [0, 1, 22, 23, 24, 25]]
            elif xalpha:
                predictions = model(X_batch)
                y_batch = 1.05*torch.ones(X_batch.shape[0], 1, device=device)
            else:
                predictions = torch.stack(model(X_batch), dim=1).to(device)
                y_batch = torch.ones(X_batch.shape[0], 3, device=device)

            loss = criterion(predictions, y_batch)
            loss.backward()

            MAE = mean_absolute_error(
                predictions.cpu().detach(), y_batch.cpu().detach()
            )
            MSE = loss.item()
            train_mse_losses_per_epoch.append(MSE)
            train_mae_losses_per_epoch.append(MAE)
            progress_bar.set_postfix(MAE=MAE, MSE=MSE)

            if ((batch_idx + 1) % accum_iter == 0) or (
                batch_idx + 1 == len(train_loader)
            ):
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)

            del X_batch, y_batch, predictions, loss, MAE, MSE
            gc.collect()
            torch.cuda.empty_cache()

        train_loss_mse.append(np.mean(train_mse_losses_per_epoch))
        train_loss_mae.append(np.mean(train_mae_losses_per_epoch))

        print(f"train MSE Loss = {train_loss_mse[epoch]:.8f}")
        print(f"train MAE Loss = {train_loss_mae[epoch]:.8f}")

        if np.mean(train_mae_losses_per_epoch) < 1e-8:
            return train_loss_mse, train_loss_mae  # Early stopping

    return train_loss_mse, train_loss_mae
