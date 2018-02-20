"""Evaluate results with a trained model."""
import os
import sys
import json
import argparse
import h5py
import numpy as np
import torch
from model import FullBiLSTM


# Disable superfluous-parens warning for python 3.
# pylint: disable=C0325

def get_img_path(img_name):
    return 'data/images/' + img_name.replace('_', '/') + '.jgp'


def predict_single_direction(ht, feats):
    scores = torch.nn.functional.log_softmax(torch.mm(ht, feats.permute(1, 0)))
    maxv, idx = torch.max(scores, 1)
    return idx, torch.exp(maxv)


def predict_multi_direction(hf, hb, feats):
    scores = torch.nn.functional.log_softmax(torch.mm(hf, feats.permute(1, 0))) + \
             torch.nn.functional.log_softmax(torch.mm(hb, feats.permute(1, 0)))
    maxv, idx = torch.max(scores, 1)
    return idx, torch.exp(maxv)


# Disable too-many-locals. No clear way to reduce them
# pylint: disable= R0914
def main(model_name, feats_name, cuda):
    """Main function."""
    outfit_file = 'data/label/fill_in_blank_test.json'
    fitb = json.load(open(outfit_file))

    data = h5py.File(feats_name, 'r')
    data_dict = dict()
    for fname, feat in zip(data['filenames'], data['features']):
        data_dict[fname] = feat

    model = FullBiLSTM(512, 512, 2480, batch_first=True, dropout=0.7)

    """Load the model weights."""
    if cuda:
        model = model.cuda()
    model.load_state_dict(torch.load(model_name))
    model.eval()

    for i, outfit in enumerate(fitb):
        sys.stdout.write('Outfit %d/%d' % (i, len(fitb)))
        sys.stdout.flush()
        question_feats = torch.from_numpy(np.array([data_dict[q] for q in outfit['question']]))
        question_feats = torch.nn.functional.normalize(question_feats, p=2, dim=1)

        answers_feats = torch.from_numpy(np.array([data_dict[a] for a in outfit['answers']]))
        answers_feats = torch.nn.functional.normalize(answers_feats, p=2, dim=1)

        if cuda:
            question_feats = question_feats.cuda()
            answers_feats = answers_feats.cuda()

        position = outfit['blank_position'] - 1

        scores = []

        if position == 0:
            out, _ = model.lstm(torch.autograd.Variable(question_feats).unsqueeze(0))
            out = out.data
            bw_hidden = out[0, :question_feats.size(0), out.size(2) // 2:][0].view(1, -1)
            pred = predict_single_direction(torch.autograd.Variable(bw_hidden),
                                            torch.autograd.Variable(answers_feats))

        elif position == len(question_feats):
            out, _ = model.lstm(torch.autograd.Variable(question_feats).unsqueeze(0))
            out = out.data
            fw_hidden = out[0, :question_feats.size(0), :out.size(2) // 2][-1].view(1, -1)
            pred = predict_single_direction(torch.autograd.Variable(fw_hidden),
                                            torch.autograd.Variable(answers_feats))

        else:
            prev = question_feats[:position]
            prev_out, _ = model.lstm(torch.autograd.Variable(prev).unsqueeze(0))
            prev_out = prev_out.data
            fw_hidden = prev_out[0, :prev.size(0), :prev_out.size(2) // 2][-1].view(1, -1)

            post = question_feats[position:]
            post_out, _ = model.lstm(torch.autograd.Variable(post).unsqueeze(0))
            post_out = post_out.data
            bw_hidden = post_out[0, :post.size(0), post_out.size(2) // 2:][0].view(1, -1)

            pred = predict_multi_direction(torch.autograd.Variable(fw_hidden),
                                           torch.autograd.Variable(bw_hidden),
                                           torch.autograd.Variable(answers_feats))

        scores.append(pred)
        import epdb; epdb.set_trace()

    print("\033[0;31m\nModel: %s\033[0m" % model_name)
    print("\033[1;30mCompatibility AUC: %f for %d outfits\033[0m" % (metrics.auc(fpr, tpr), len(labels)))


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--model_path', '-m', type=str, help='path to the model', default='')
    PARSER.add_argument('--feats_path', '-sp', type=str, help='path to the features', default='')
    PARSER.add_argument('--cuda', dest='cuda', help='use cuda', action='store_true')
    PARSER.add_argument('--no-cuda', dest='cuda', help="don't use cuda", action='store_false')
    PARSER.set_defaults(cuda=True)
    ARGS = PARSER.parse_args()

    main(ARGS.model_path, ARGS.feats_path, ARGS.cuda)